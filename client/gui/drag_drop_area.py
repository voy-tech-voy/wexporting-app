"""
Drag and Drop Area Widget
Handles file drag and drop operations for the graphics converter
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QFileDialog, QMessageBox, QStyledItemDelegate, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QSize, QByteArray, QObject
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QIcon, QAction, QPainter, QColor, QCursor, QBrush
from PyQt6.QtSvg import QSvgRenderer
import os
import subprocess
import tempfile
import re
from pathlib import Path
from client.utils.resource_path import get_resource_path
from client.gui.theme import Theme
from client.gui.custom_widgets import PresetStatusButton, HoverIconButton, FileListItemWidget

# Import refactored helper modules
from client.core import file_type_utils
from client.gui.styles import drag_drop_styler
from client.gui.widgets.placeholder_widget import DropPlaceholderWidget
from client.gui.dialogs import drop_dialogs
from client.gui.components import toast_helpers
from client.gui.components import file_context_menu

from enum import Enum


class ViewMode(Enum):
    """View modes for the DragDropArea smart container."""
    FILES = "files"      # Show file list (default)
    PRESETS = "presets"  # Show preset gallery overlay


class DragDropArea(QWidget):
    """
    Smart Container for file management with overlay support.
    
    Implements the Mediator-Shell pattern:
    - Manages multiple view modes (FILES, PRESETS)
    - Exposes set_view_mode() API for external control
    - Emits signals for parent coordination
    """
    
    files_added = pyqtSignal(list)  # Signal emitted when files are added
    preset_applied = pyqtSignal(object, list)  # Emits (preset, files) when preset selected
    view_mode_changed = pyqtSignal(str)  # Emits new view mode name
    go_to_lab_requested = pyqtSignal(dict)  # Emits lab_mode_settings when "Go to Lab" is clicked
    
    # Note: SUPPORTED_EXTENSIONS moved to client.core.file_type_utils
    
    def __init__(self):
        super().__init__()
        self.file_list = []
        self.theme_manager = None  # Will be set by parent
        self._is_converting = False # State flag to gate status clearing
        self.setAcceptDrops(True)  # Enable drag/drop on the main widget
        self._current_processing_index = -1  # Track which file is being processed
        self._pending_files = None  # Files waiting for preset selection
        self._current_view_mode = ViewMode.FILES  # Default view mode
        self._group_sequences = True # Default state for sequence grouping
        self.setup_ui()
    
    def set_file_progress(self, file_index, progress):
        """Set progress for a specific file in the list (0.0 to 1.0) - No-op now"""
        # Progress display removed - only show completion
        pass
    
    def eventFilter(self, source, event):
        """Handle events for child widgets"""
        # Clear statuses when clicking empty space in list (unless persistence is enabled)
        if (source == self.file_list_widget.viewport() and 
            event.type() == QEvent.Type.MouseButtonPress):
            from client.gui.dev_panels.noise_params import NoiseParams
            if not NoiseParams.persistence_enabled:
                self.clear_all_statuses()
            
        return super().eventFilter(source, event)

    def set_file_completed(self, file_index):
        """Mark a file as completed"""
        self.set_file_status(file_index, 'success')

    def set_file_status(self, file_index: int, status: str):
        """Set visual status for a file item. status: 'success'|'skipped'|'failed'|'stopped'"""
        # Validate index against master file list
        if not (0 <= file_index < len(self.file_list)):
            return

        file_path = self.file_list[file_index]
        
        # 1. Check Sequence View Mode
        if self.current_view_mode == ViewMode.FILES and self._group_sequences:
            # Find the widget containing this file
            for i in range(self.file_list_widget.count()):
                item = self.file_list_widget.item(i)
                widget = self.file_list_widget.itemWidget(item)
                
                if widget and getattr(widget, 'is_sequence', False):
                    if hasattr(widget, 'sequence_files') and file_path in widget.sequence_files:
                        # Found sequence!
                        if status == 'success':
                            # Set intermediate status to trigger paintEvent but NOT full completion logic yet
                            widget.set_status('processing') 
                            widget.mark_file_complete(file_path)
                        elif status in ['failed', 'skipped', 'stopped']:
                            # For now, just mark as complete so progress continues? 
                            # Or maybe mark as failed? 
                            # Let's count it as complete for progress bar purposes, 
                            # but if it fails, the bar might need a mixed color?
                            # Simple approach: Mark complete so bar fills.
                            widget.mark_file_complete(file_path)
                            
                        return
                    
                # Also check single items in sequence view (they might not be is_sequence=True)
                # But if they are single, file_index mapping might be tricky if we don't scan.
                # Actually, simpler: just scan all widgets.
                elif widget and widget.file_path == file_path:
                     widget.set_status(status)
                     if status == 'success':
                         item.setData(Qt.ItemDataRole.UserRole + 1, True)
                     return

        # 2. Standard View (or Fallback)
        # If NOT in sequence mode, file_index should match row index (mostly)
        # BUT safely, we should probably find by path or trust index if counts match
        if 0 <= file_index < self.file_list_widget.count():
             # Basic 1:1 mapping (Process: legacy logic relied on this)
             # But to be safe with new DragDropArea refactor, let's double check path?
             # For now, stick to index if counts match, else scan.
             if len(self.file_list) == self.file_list_widget.count():
                item = self.file_list_widget.item(file_index)
                if status == 'success':
                    item.setData(Qt.ItemDataRole.UserRole + 1, True)
                
                widget = self.file_list_widget.itemWidget(item)
                if widget and hasattr(widget, 'set_status'):
                    widget.set_status(status)
             else:
                 # Counts mismatch (maybe filtering?), scan for path
                 for i in range(self.file_list_widget.count()):
                     item = self.file_list_widget.item(i)
                     widget = self.file_list_widget.itemWidget(item)
                     if widget and widget.file_path == file_path:
                         widget.set_status(status)
                         if status == 'success':
                             item.setData(Qt.ItemDataRole.UserRole + 1, True)
                         return

    def clear_all_statuses(self):
        """Clear visual status from all files"""
        if self._is_converting:
            return
            
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            widget = self.file_list_widget.itemWidget(item)
            if widget:
                # Clear status AND progress (critical for sequences)
                if hasattr(widget, 'clear_progress'):
                    widget.clear_progress()
                elif hasattr(widget, 'clear_status'):
                    widget.clear_status()
                
            # Clear item data
            item.setData(Qt.ItemDataRole.UserRole + 1, None)

    def set_converting(self, is_converting: bool):
        """Set conversion state to gate status clearing"""
        self._is_converting = is_converting
    # NOTE: set_preset_active removed - preset_status_btn is now in MainWindow's control bar
    # State updates go through the preset_applied signal handled by MainWindow.on_preset_applied
    
    def clear_all_progress(self):
        """Clear progress indicators from all files"""
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            widget = self.file_list_widget.itemWidget(item)
            if widget:
                if hasattr(widget, 'clear_progress'):
                    widget.clear_progress()
                if hasattr(widget, 'clear_status'):
                    widget.clear_status()
        self._current_processing_index = -1
        
    def setup_ui(self):
        """Setup the drag and drop interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Note: File buttons and Preset button have been moved to MainWindow control bar
        
        # Combined file list widget that serves as both drop area and display
        self.file_list_widget = QListWidget()
        self.file_list_widget.setObjectName("DropZone")  # V4.0 branding
        self.file_list_widget.setMinimumHeight(300)
        
        # Disable Selection! (Allow only highlight)
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list_widget.viewport().installEventFilter(self) # Detect clicks on empty space
        
        # Disable dashed focus rectangle
        self.file_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # Disable horizontal scrollbar
        self.file_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Initial styling will be set by theme manager
        self.reset_list_style()
        
        # Disable drag/drop on the list widget - we handle it on the parent
        self.file_list_widget.setAcceptDrops(False)
        
        # Connect double-click to remove file
        self.file_list_widget.itemDoubleClicked.connect(self.remove_file_item)
        
        # Add keyboard delete functionality
        self.file_list_widget.keyPressEvent = self.handle_list_key_press
        
        # Add context menu for file operations
        self.file_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.file_list_widget)
        
        # Initialize with cleared state
        self.file_list_widget.clear()
        
    def _setup_preset_plugin(self, conversion_conductor=None):
        """
        Setup the preset plugin inside the drop area.
        
        Initializes PresetOrchestrator with the ToolRegistry and ConversionConductor,
        connecting logic and UI layers.
        
        Args:
            conversion_conductor: ConversionConductor for lab mode preset execution (optional)
        """
        try:
            from client.core.tool_registry import get_registry
            from client.plugins.presets import PresetOrchestrator
            
            registry = get_registry()
            # Parent gallery to DragDropArea (self) not file_list_widget for full width
            self._preset_orchestrator = PresetOrchestrator(registry, self, conversion_conductor)
            self._preset_orchestrator.preset_selected.connect(self._on_preset_selected)
            self._preset_orchestrator.gallery_dismissed.connect(self._on_preset_dismissed)
            self._preset_orchestrator.go_to_lab_requested.connect(self._on_go_to_lab_requested)
            print(f"[DragDropArea] Preset plugin initialized with {len(self._preset_orchestrator.presets)} presets")
        except Exception as e:
            print(f"[DragDropArea] Failed to initialize preset plugin: {e}")
            self._preset_orchestrator = None
    
    def ensure_preset_orchestrator(self):
        """
        Ensure preset orchestrator is initialized. Called by CommandPanel.
        
        Returns:
            PresetOrchestrator instance or None if initialization failed
        """
        if not hasattr(self, '_preset_orchestrator') or self._preset_orchestrator is None:
            print("[DragDropArea] Initializing preset plugin for custom preset creation")
            self._setup_preset_plugin()
        return self._preset_orchestrator
    
    def _on_preset_selected(self, preset):
        """Handle preset selection from the gallery."""
        print(f"[DragDropArea] Preset selected: {preset.name}")
        # Emit signal for parent to handle
        self.preset_applied.emit(preset, self.file_list)
    
    def _on_preset_dismissed(self):
        """Handle gallery dismissal."""
        print("[DragDropArea] Preset gallery dismissed")
        self._current_view_mode = ViewMode.FILES
        self.view_mode_changed.emit(ViewMode.FILES.value)
    
    def _on_go_to_lab_requested(self, lab_settings: dict):
        """Forward go to lab request via signal."""
        print(f"[DragDropArea] Go to Lab requested with {len(lab_settings)} settings")
        self.go_to_lab_requested.emit(lab_settings)
        
    def toggle_sequence_view(self, checked):
        """Toggle between flat and sequence view"""
        self._group_sequences = checked
        self.refresh_file_list()

    def refresh_file_list(self):
        """Rebuild list widget based on current files and view mode"""
        self.file_list_widget.clear()
        
        if self._group_sequences:
            from client.utils.sequence_detector import SequenceDetector
            sequences, singles = SequenceDetector.detect(self.file_list)
            
            # Add sequences
            for seq in sequences:
                display_name = f"{seq['name']} ({seq['count']} files)"
                first_file = seq['preview_file']
                
                item = QListWidgetItem()
                item.setToolTip(f"Sequence: {seq['name']}\nFiles: {seq['count']}\nRange: {seq['range'][0]}-{seq['range'][1]}")
                
                item_widget = FileListItemWidget(display_name, first_file, self) # Use preview file for thumbnail
                item_widget.set_sequence_mode(seq['count'], seq['files']) # Enable stacked display
                
                # Apply style
                is_dark = self.theme_manager and self.theme_manager.current_theme == 'dark'
                item_widget.update_button_style(is_dark)
                
                # Logic for removal
                self._connect_item_signals(item, item_widget, is_sequence=True, sequence_files=seq['files'])
                
                item.setSizeHint(item_widget.sizeHint())
                self.file_list_widget.addItem(item)
                self.file_list_widget.setItemWidget(item, item_widget)
            
            # Add singles
            for file_path in singles:
                self._add_single_file_item(file_path)
                
        else:
            # Flat list
            for file_path in self.file_list:
                self._add_single_file_item(file_path)
        
        self.update_placeholder_text()

    def _add_single_file_item(self, file_path):
        """Helper to add a single file item"""
        file_name = os.path.basename(file_path)
        file_size = file_type_utils.get_file_size(file_path)
        item_text = f"{file_name} ({file_size})"
        
        item = QListWidgetItem()
        item.setToolTip(f"Full path: {file_path}\nSize: {file_size}")
        
        item_widget = FileListItemWidget(item_text, file_path, self)
        is_dark = self.theme_manager and self.theme_manager.current_theme == 'dark'
        item_widget.update_button_style(is_dark)
        
        self._connect_item_signals(item, item_widget)
        
        item.setSizeHint(item_widget.sizeHint())
        self.file_list_widget.addItem(item)
        self.file_list_widget.setItemWidget(item, item_widget)
        
    def _connect_item_signals(self, item, item_widget, is_sequence=False, sequence_files=None):
        """Connect signals for list items"""
        def create_remove_handler(widget, is_seq, seq_files):
            def handler():
                # Remove logic
                if is_seq and seq_files:
                    # Remove all files in sequence from main list
                    for f in seq_files:
                        if f in self.file_list:
                            self.file_list.remove(f)
                else:
                    # Single file removal
                    if widget.file_path in self.file_list:
                         self.file_list.remove(widget.file_path)
                
                # Full refresh to update list
                self.refresh_file_list()
            return handler
        
        item_widget.remove_clicked.connect(create_remove_handler(item_widget, is_sequence, sequence_files))
        item_widget.status_clicked.connect(self.clear_all_statuses)
    
    # =========================================================================
    # SMART CONTAINER API (Mediator-Shell Pattern)
    # =========================================================================
    
    def set_view_mode(self, mode: ViewMode):
        """
        Switch the container's view mode.
        
        This is the primary API for external controllers (MainWindow) to
        switch between file list and preset gallery views.
        
        Args:
            mode: ViewMode.FILES or ViewMode.PRESETS
        """
        if self._current_view_mode == mode:
            return
        
        self._current_view_mode = mode
        
        if mode == ViewMode.PRESETS:
            self._show_preset_overlay()
        else:
            self._hide_preset_overlay()
        
        # Refresh placeholder visibility based on new mode
        self.update_placeholder_text()
        
        self.view_mode_changed.emit(mode.value)
    
    @property
    def current_view_mode(self) -> ViewMode:
        """Get the current view mode."""
        return self._current_view_mode
    
    def _show_preset_overlay(self):
        """Internal: Show the preset gallery overlay."""
        if hasattr(self, '_preset_orchestrator') and self._preset_orchestrator:
            self._preset_orchestrator.show_gallery()
        else:
            print("[DEBUG] Preset plugin not initialized - initializing now")
            self._setup_preset_plugin()
            if self._preset_orchestrator:
                self._preset_orchestrator.show_gallery()
    
    def _hide_preset_overlay(self):
        """Internal: Hide the preset gallery overlay."""
        if hasattr(self, '_preset_orchestrator') and self._preset_orchestrator:
            self._preset_orchestrator.hide_gallery()
    
    # --- Backward Compatibility Methods ---
    
    def show_preset_view(self):
        """Show the preset gallery overlay. (Backward compatible)"""
        self.set_view_mode(ViewMode.PRESETS)
    
    def hide_preset_view(self):
        """Hide the preset gallery overlay. (Backward compatible)"""
        self.set_view_mode(ViewMode.FILES)
    
    def resizeEvent(self, event):
        """Update placeholder size and overlay geometry"""
        super().resizeEvent(event)
        
        # NOTE: Preset overlay removed - resize handled by future plugin
        
        if hasattr(self, 'file_list_widget') and self.file_list_widget.count() == 1:
            item = self.file_list_widget.item(0)
            if item and item.data(Qt.ItemDataRole.UserRole) == "PLACEHOLDER":
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(10, self.update_placeholder_size)

    def update_placeholder_size(self):
        """Specifically update the placeholder item size to match viewport"""
        if hasattr(self, 'file_list_widget') and self.file_list_widget.count() == 1:
            item = self.file_list_widget.item(0)
            if item and item.data(Qt.ItemDataRole.UserRole) == "PLACEHOLDER":
                viewport_size = self.file_list_widget.viewport().size()
                if viewport_size.height() > 50:
                    item.setSizeHint(viewport_size)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter - accept files for processing"""
        if self._is_converting:
            event.ignore()
            return
            
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        """Handle drag leave"""
        event.accept()
        
    def dropEvent(self, event: QDropEvent):
        """Handle dropped files - add them to the list immediately"""
        if self._is_converting:
            event.ignore()
            return

        if event.mimeData().hasUrls():
            files = []
            folders = []
            
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    files.append(path)
                elif os.path.isdir(path):
                    folders.append(path)
            
            # Collect all files including from folders
            all_files = files.copy()
            for folder in folders:
                folder_files = file_type_utils.get_supported_files_from_folder(folder, True)
                all_files.extend(folder_files)
            
            # Add files directly to the list
            if all_files:
                self.add_files(all_files)
            
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def handle_dropped_folders(self, folders):
        """Handle dropped folder(s) with user options"""
        files = drop_dialogs.show_folder_drop_dialog(
            self, folders, self.theme_manager,
            file_type_utils.count_supported_files,
            file_type_utils.get_supported_files_from_folder
        )
        
        if files:
            self.add_files(files)
            self.update_status(f"Added {len(files)} files from {len(folders)} folder(s)")
        elif files is not None:  # Empty list (no files found)
            QMessageBox.information(self, "No Files Found", "No supported files found in the dropped folder(s).")
                
    def update_status(self, message):
        """Emit a status update (to be connected by parent)"""
        # This will be connected to the main window's update_status method
        pass
        
    def on_drag_enter(self):
        """Handle drag enter visual feedback"""
        if self.theme_manager:
            is_dark = self.theme_manager.current_theme == 'dark'
            styles = self.theme_manager.get_drag_drop_styles()
            full_style = styles['drag_over'] + drag_drop_styler.get_scrollbar_style(is_dark)
            self.file_list_widget.setStyleSheet(full_style)
        
    def on_drag_leave(self):
        """Handle drag leave visual feedback"""
        self.reset_list_style()
        
    def reset_list_style(self):
        """Reset the list widget to default style using V4.0 Theme Variables"""
        is_dark = True
        if self.theme_manager:
            is_dark = self.theme_manager.current_theme == 'dark'
        
        Theme.set_dark_mode(is_dark)
        
        # If list is empty, use transparent background for placeholder
        if len(self.file_list) == 0:
            bg_color = "transparent"
        else:
            bg_color = Theme.surface_drop_area()
        
        # Use styling helper
        base_style = drag_drop_styler.get_list_style(is_dark, bg_color)
        scrollbar_style = drag_drop_styler.get_scrollbar_style(is_dark)
        full_style = base_style + scrollbar_style
        self.file_list_widget.setStyleSheet(full_style)
        
        # Restore completion backgrounds for completed items
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            if item:
                widget = self.file_list_widget.itemWidget(item)
                if widget and hasattr(widget, 'update_theme'):
                    widget.update_theme(is_dark)
    
    def _apply_scrollbar_style(self):
        """Apply scrollbar styling to the file list widget"""
        self.reset_list_style()
    
    def set_theme_manager(self, theme_manager):
        """Set the theme manager and apply current theme"""
        self.theme_manager = theme_manager
        # Only update styles, don't clear files (preserves list when switching themes)
        self.reset_list_style()
        self.update_placeholder_text()
        
        # Propagate theme to preset orchestrator
        if hasattr(self, '_preset_orchestrator') and self._preset_orchestrator:
            is_dark = theme_manager.current_theme == 'dark'
            self._preset_orchestrator.update_theme(is_dark)
        
    def add_files_dialog(self):
        """Open file dialog to add files"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select files for conversion",
            "",
            "All Supported (*.jpg *.jpeg *.png *.bmp *.tiff *.gif *.svg *.mp4 *.avi *.mov *.mkv *.mp3 *.wav);;Images (*.jpg *.jpeg *.png *.bmp *.tiff *.gif *.svg);;Videos (*.mp4 *.avi *.mov *.mkv);;Audio (*.mp3 *.wav *.flac);;All Files (*)"
        )
        
        if files:
            self.add_files(files)
            
    def add_folder_dialog(self):
        """Open folder dialog to add all supported files from a directory"""
        files = drop_dialogs.show_add_folder_dialog(
            self, self.theme_manager,
            file_type_utils.count_supported_files,
            file_type_utils.get_supported_files_from_folder
        )
        
        if files:
            self.add_files(files)
        elif files is not None:  # Empty list
            QMessageBox.information(self, "No Files Found", "No supported files found in the selected folder.")
            
    def add_files(self, files):
        """Add files to the conversion list"""
        added_files = []
        unsupported_count = 0
        files_actually_added = False
        
        for file_path in files:
            if file_path not in self.file_list:
                # Skip cryptomatte files (FFmpeg can't decode them properly)
                file_name = Path(file_path).name.lower()
                if 'cryptomatte' in file_name:
                    unsupported_count += 1
                    continue
                    
                # Check if file type is supported
                file_ext = Path(file_path).suffix.lower()
                if self.is_supported_file(file_ext):
                    self.file_list.append(file_path)
                    added_files.append(file_path)
                    files_actually_added = True
                    
                    # Only add directly if NOT in sequence mode
                    if not self._group_sequences:
                        self._add_single_file_item(file_path)
                else:
                    unsupported_count += 1
        
        # If in sequence mode, full refresh is safer
        if files_actually_added and self._group_sequences:
            self.refresh_file_list()
        
        # Show single consolidated toast if there were unsupported files
        if unsupported_count > 0:
            self.show_unsupported_files_toast(unsupported_count)
                    
        if added_files:
            self.files_added.emit(added_files)
            self.update_placeholder_text()
            
    def is_supported_file(self, extension):
        """Check if file extension is supported"""
        return file_type_utils.is_supported_file(extension)
        
    def clear_files(self):
        """Clear all files from the list"""
        self.file_list.clear()
        self.file_list_widget.clear()
        self.update_placeholder_text()
        
        # Invalidate preset gallery blur cache so it shows empty background
        if hasattr(self, '_preset_orchestrator') and self._preset_orchestrator:
            if hasattr(self._preset_orchestrator, '_gallery') and self._preset_orchestrator._gallery:
                self._preset_orchestrator._gallery.clear_blur_cache()
        
    def update_placeholder_text(self):
        """Update placeholder - show centered widget when empty"""
        if len(self.file_list) == 0:
            # Don't show placeholder when in PRESETS view mode (gallery is open)
            if self._current_view_mode == ViewMode.PRESETS:
                self.file_list_widget.clear()
                return
            
            # Clear all items first to avoid duplicates
            self.file_list_widget.clear()
            
            # Create placeholder widget
            placeholder = DropPlaceholderWidget()
            
            # Get current style and apply placeholder-specific overrides
            if self.theme_manager:
                styles = self.theme_manager.get_drag_drop_styles()
                base_style = styles['normal']
            else:
                base_style = ""
            
            is_dark = self.theme_manager and self.theme_manager.current_theme == 'dark'
            modified_style = drag_drop_styler.get_placeholder_style(is_dark, base_style)
            self.file_list_widget.setStyleSheet(modified_style)
            
            # Add placeholder to list widget
            item = QListWidgetItem()
            viewport_size = self.file_list_widget.viewport().size()
            if viewport_size.height() < 100:
                item.setSizeHint(self.file_list_widget.size())
            else:
                item.setSizeHint(viewport_size)
            item.setBackground(Qt.GlobalColor.transparent)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setData(Qt.ItemDataRole.UserRole, "PLACEHOLDER")
            self.file_list_widget.addItem(item)
            self.file_list_widget.setItemWidget(item, placeholder)
            
        else:
            # Remove any placeholder items if files are present
            items_to_remove = []

            for i in range(self.file_list_widget.count()):
                item = self.file_list_widget.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == "PLACEHOLDER":
                    items_to_remove.append(i)
            
            # Remove placeholder items in reverse order
            for i in reversed(items_to_remove):
                self.file_list_widget.takeItem(i)
            
            # Restore original list widget styling
            self.reset_list_style()


                    


                    
    def remove_file_by_index(self, index):
        """Remove a file by its index in the list"""
        if 0 <= index < len(self.file_list):
            # Remove from file list
            self.file_list.pop(index)
            
            # Remove from widget
            self.file_list_widget.takeItem(index)
            
            # Update placeholder if empty
            self.update_placeholder_text()
            
    def remove_file_item(self, item):
        """Remove a file item when double-clicked"""
        if item:
            row = self.file_list_widget.row(item)
            if 0 <= row < len(self.file_list):
                self.remove_file_by_index(row)
    
    def show_insufficient_credits_toast(self):
        """Show a large, centered toast for insufficient energy."""
        toast_helpers.show_insufficient_energy_toast(self)

    def show_unsupported_files_toast(self, count):
        """Show a toast notification for unsupported files"""
        toast_helpers.show_unsupported_files_toast(self, count)

    def show_conversion_toast(self, successful: int, failed: int, skipped: int, stopped: int):
        """
        Show conversion results in a toast notification with color-coded details.
        Replaces the old modal dialog.
        """
        toast_helpers.show_conversion_toast(self, successful, failed, skipped, stopped)
            
    def handle_list_key_press(self, event):
        """Handle keyboard events for the file list"""
        from PyQt6.QtCore import Qt
        
        # Handle Delete and Backspace keys to remove selected items
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected_items = self.file_list_widget.selectedItems()
            if selected_items:
                # Remove items in reverse order to maintain visual consistency during removal?
                # Actually, if we rebuild list, order doesn't matter much but efficient to remove from widget.
                # But we are modifying self.file_list.
                
                files_removed = False
                
                for item in selected_items:
                    if item.data(Qt.ItemDataRole.UserRole) == "PLACEHOLDER":
                        continue
                        
                    widget = self.file_list_widget.itemWidget(item)
                    if widget:
                        # Check if sequence
                        if getattr(widget, 'is_sequence', False) and hasattr(widget, 'sequence_files'):
                            for f in widget.sequence_files:
                                if f in self.file_list:
                                    self.file_list.remove(f)
                                    files_removed = True
                        elif hasattr(widget, 'file_path') and widget.file_path:
                            if widget.file_path in self.file_list:
                                self.file_list.remove(widget.file_path)
                                files_removed = True
                
                if files_removed:
                    self.refresh_file_list()
        else:
            # Call the original key press event handler for other keys
            QListWidget.keyPressEvent(self.file_list_widget, event)
            
    def show_context_menu(self, position):
        """Show context menu for file operations"""
        file_context_menu.show_file_context_menu(
            self, self.file_list_widget, position, self.theme_manager,
            self.remove_file_item, self._show_in_explorer_wrapper,
            sequences_enabled=self._group_sequences,
            on_toggle_sequences=self.toggle_sequence_view
        )
    
    def _show_in_explorer_wrapper(self, item):
        """Wrapper to extract file path and call explorer helper"""
        if item and item.data(Qt.ItemDataRole.UserRole) != "PLACEHOLDER":
            row = self.file_list_widget.row(item)
            if 0 <= row < len(self.file_list):
                file_path = self.file_list[row]
                file_context_menu.show_in_explorer(file_path)
            


    def get_files(self, grouped=False):
        """
        Return the list of files to be converted.
        
        Args:
            grouped: If True, returns a combined list where sequences are 
                    represented as dicts and singles as strings.
        """
        if not grouped:
            return self.file_list.copy()
            
        from client.utils.sequence_detector import SequenceDetector
        sequences, singles = SequenceDetector.detect(self.file_list)
        return sequences + singles


