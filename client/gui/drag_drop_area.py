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
    
    # Supported file extensions for graphics conversion
    SUPPORTED_EXTENSIONS = {
        'images': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp', '.gif', '.svg'],
        'videos': ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.m4v'],
        'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']
    }
    
    def __init__(self):
        super().__init__()
        self.file_list = []
        self.theme_manager = None  # Will be set by parent
        self.setAcceptDrops(True)  # Enable drag/drop on the main widget
        self._current_processing_index = -1  # Track which file is being processed
        self._pending_files = None  # Files waiting for preset selection
        self._current_view_mode = ViewMode.FILES  # Default view mode
        self.setup_ui()
    
    def set_file_progress(self, file_index, progress):
        """Set progress for a specific file in the list (0.0 to 1.0) - No-op now"""
        # Progress display removed - only show completion
        pass
    
    def eventFilter(self, source, event):
        """Handle events for child widgets"""
        # Clear statuses when clicking empty space in list
        if (source == self.file_list_widget.viewport() and 
            event.type() == QEvent.Type.MouseButtonPress):
            self.clear_all_statuses()
            
        return super().eventFilter(source, event)

    def set_file_completed(self, file_index):
        """Mark a file as completed"""
        self.set_file_status(file_index, 'success')

    def set_file_status(self, file_index: int, status: str):
        """Set visual status for a file item. status: 'success'|'skipped'|'failed'|'stopped'"""
        if 0 <= file_index < self.file_list_widget.count():
            item = self.file_list_widget.item(file_index)
            # Store completion state in item data
            if status == 'success':
                item.setData(Qt.ItemDataRole.UserRole + 1, True)
            
            # Update widget status
            widget = self.file_list_widget.itemWidget(item)
            if widget and hasattr(widget, 'set_status'):
                widget.set_status(status)

    def clear_all_statuses(self):
        """Clear visual status from all files"""
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            widget = self.file_list_widget.itemWidget(item)
            if widget and hasattr(widget, 'clear_status'):
                widget.clear_status()

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
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        """Handle drag leave"""
        event.accept()
        
    def dropEvent(self, event: QDropEvent):
        """Handle dropped files - add them to the list immediately"""
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
                folder_files = self.get_supported_files_from_folder(folder, True)
                all_files.extend(folder_files)
            
            # Add files directly to the list
            if all_files:
                self.add_files(all_files)
            
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def _apply_dialog_styling(self, dialog):
        """Apply consistent rounded corner styling to dialogs"""
        is_dark = self.theme_manager and self.theme_manager.current_theme == 'dark'
        Theme.set_dark_mode(is_dark)
        
        base_styles = self.theme_manager.get_dialog_styles() if self.theme_manager else ""
        
        rounded_style = f"""
            QDialog {{
                background-color: {Theme.surface_element()};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """
        
        dialog.setStyleSheet(base_styles + rounded_style)
        
    def handle_dropped_folders(self, folders):
        """Handle dropped folder(s) with user options"""
        from PyQt6.QtWidgets import QCheckBox, QVBoxLayout, QDialog, QDialogButtonBox, QLabel
        
        if len(folders) == 1:
            folder_name = os.path.basename(folders[0])
            title = f"Process Folder: {folder_name}"
        else:
            title = f"Process {len(folders)} Folders"
            
        # Create options dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Folder Drop Options")
        dialog.setFixedSize(400, 250)
        
        # Apply consistent rounded corner styling
        self._apply_dialog_styling(dialog)
        
        layout = QVBoxLayout(dialog)
        
        if len(folders) == 1:
            layout.addWidget(QLabel(f"Dropped folder: {folder_name}"))
        else:
            layout.addWidget(QLabel(f"Dropped {len(folders)} folder(s):"))
            for folder in folders[:3]:  # Show first 3
                layout.addWidget(QLabel(f"• {os.path.basename(folder)}"))
            if len(folders) > 3:
                layout.addWidget(QLabel(f"• ... and {len(folders) - 3} more"))
                
        layout.addWidget(QLabel("\nChoose processing options:"))
        
        # Include subfolders option
        include_subfolders = QCheckBox("Include subfolders (recursive)")
        include_subfolders.setChecked(False)
        layout.addWidget(include_subfolders)
        
        # Show file count preview
        preview_label = QLabel("")
        layout.addWidget(preview_label)
        
        def update_preview():
            total_count = 0
            for folder in folders:
                total_count += self.count_supported_files(folder, include_subfolders.isChecked())
            preview_label.setText(f"Found {total_count} supported file(s) total")
        
        include_subfolders.toggled.connect(update_preview)
        update_preview()  # Initial count
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            all_files = []
            for folder in folders:
                folder_files = self.get_supported_files_from_folder(folder, include_subfolders.isChecked())
                all_files.extend(folder_files)
                
            if all_files:
                self.add_files(all_files)
                self.update_status(f"Added {len(all_files)} files from {len(folders)} folder(s)")
            else:
                QMessageBox.information(self, "No Files Found", "No supported files found in the dropped folder(s).")
                
    def update_status(self, message):
        """Emit a status update (to be connected by parent)"""
        # This will be connected to the main window's update_status method
        pass
        
    def on_drag_enter(self):
        """Handle drag enter visual feedback"""
        if self.theme_manager:
            styles = self.theme_manager.get_drag_drop_styles()
            full_style = styles['drag_over'] + self._get_scrollbar_style()
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
        
        # Base DropZone style
        base_style = f"""
            QListWidget#DropZone {{
                background-color: {bg_color};
                border: 6px dashed {Theme.border()};
                border-radius: {Theme.RADIUS_LG}px;
                color: {Theme.text()};
                font-size: {Theme.FONT_SIZE_BASE}px;
                padding: 0px;
                outline: none;
            }}
            QListWidget#DropZone:hover {{
                border-color: {Theme.border_focus()};
                background-color: {bg_color};
            }}
        """
        # Append scrollbar styling
        full_style = base_style + self._get_scrollbar_style()
        self.file_list_widget.setStyleSheet(full_style)
        
        # Restore completion backgrounds for completed items
        for i in range(self.file_list_widget.count()):
            item = self.file_list_widget.item(i)
            if item:
                # Update widget theme colors (this also restores completion background if applicable)
                widget = self.file_list_widget.itemWidget(item)
                if widget and hasattr(widget, 'update_theme'):
                    widget.update_theme(is_dark)
            
    def _get_scrollbar_style(self):
        """Get modern minimalistic scrollbar styling with grey item selection"""
        is_dark = self.theme_manager and self.theme_manager.current_theme == 'dark'
        Theme.set_dark_mode(is_dark)
        
        # Common colors from Theme
        item_selected_bg = Theme.color("surface_hover")
        item_hover_bg = Theme.color("surface_pressed") if is_dark else Theme.color("surface_hover")
        text_color = Theme.text()
        scrollbar_bg = Theme.color("scrollbar_bg")
        scrollbar_thumb = Theme.color("scrollbar_thumb")
        scrollbar_thumb_hover = Theme.border_focus()
        
        return f"""
            QListWidget::item {{
                outline: none;
                border: none;
            }}
            QListWidget::item:selected {{
                background-color: {item_selected_bg};
                color: {text_color};
                outline: none;
                border: none;
            }}
            QListWidget::item:focus {{
                outline: none;
                border: none;
            }}
            QListWidget::item:selected:focus {{
                background-color: {item_selected_bg};
                outline: none;
                border: none;
            }}
            QListWidget::item:hover:!selected {{
                background-color: transparent;
                border-radius: {Theme.RADIUS_MD}px;
            }}
            QScrollBar:vertical {{
                background: {scrollbar_bg};
                width: 10px;
                border: none;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {scrollbar_thumb};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scrollbar_thumb_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background: {scrollbar_bg};
                height: 10px;
                border: none;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background: {scrollbar_thumb};
                border-radius: 5px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {scrollbar_thumb_hover};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """
    
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
        from PyQt6.QtWidgets import QFileDialog, QCheckBox, QVBoxLayout, QDialog, QDialogButtonBox, QLabel
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select folder to process all supported files",
            ""
        )
        
        if folder:
            # Create options dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Folder Processing Options")
            dialog.setFixedSize(400, 200)
            
            # Apply consistent rounded corner styling
            self._apply_dialog_styling(dialog)
            
            layout = QVBoxLayout(dialog)
            
            layout.addWidget(QLabel(f"Selected folder: {os.path.basename(folder)}"))
            layout.addWidget(QLabel("Choose processing options:"))
            
            # Include subfolders option
            include_subfolders = QCheckBox("Include subfolders (recursive)")
            include_subfolders.setChecked(False)
            layout.addWidget(include_subfolders)
            
            # Show file count preview
            preview_label = QLabel("")
            layout.addWidget(preview_label)
            
            def update_preview():
                count = self.count_supported_files(folder, include_subfolders.isChecked())
                preview_label.setText(f"Found {count} supported file(s)")
            
            include_subfolders.toggled.connect(update_preview)
            update_preview()  # Initial count
            
            # Dialog buttons
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                files = self.get_supported_files_from_folder(folder, include_subfolders.isChecked())
                if files:
                    self.add_files(files)
                else:
                    QMessageBox.information(self, "No Files Found", "No supported files found in the selected folder.")
                    
    def count_supported_files(self, folder_path, include_subfolders=False):
        """Count supported files in folder"""
        count = 0
        folder = Path(folder_path)
        
        if include_subfolders:
            # Recursive search
            for file_path in folder.rglob('*'):
                if file_path.is_file() and self.is_supported_file(file_path.suffix.lower()):
                    count += 1
        else:
            # Only direct files in folder
            for file_path in folder.iterdir():
                if file_path.is_file() and self.is_supported_file(file_path.suffix.lower()):
                    count += 1
                    
        return count
        
    def get_supported_files_from_folder(self, folder_path, include_subfolders=False):
        """Get list of supported files from folder"""
        files = []
        folder = Path(folder_path)
        
        try:
            if include_subfolders:
                # Recursive search
                for file_path in folder.rglob('*'):
                    if file_path.is_file() and self.is_supported_file(file_path.suffix.lower()):
                        files.append(str(file_path))
            else:
                # Only direct files in folder
                for file_path in folder.iterdir():
                    if file_path.is_file() and self.is_supported_file(file_path.suffix.lower()):
                        files.append(str(file_path))
                        
            # Sort files for consistent ordering
            files.sort()
            
        except PermissionError:
            QMessageBox.warning(self, "Access Denied", f"Cannot access folder: {folder_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error reading folder: {str(e)}")
            
        return files
            
    def add_files(self, files):
        """Add files to the conversion list"""
        added_files = []
        unsupported_count = 0
        
        for file_path in files:
            if file_path not in self.file_list:
                # Check if file type is supported
                file_ext = Path(file_path).suffix.lower()
                if self.is_supported_file(file_ext):
                    self.file_list.append(file_path)
                    added_files.append(file_path)
                    
                    # Add to list widget with file info
                    file_name = os.path.basename(file_path)
                    file_size = self.get_file_size(file_path)
                    item_text = f"{file_name} ({file_size})"
                    
                    # Create custom widget for the item
                    item = QListWidgetItem()
                    item.setToolTip(f"Full path: {file_path}\nSize: {file_size}")
                    
                    # Create custom widget with remove button and thumbnail
                    item_widget = FileListItemWidget(item_text, file_path, self)
                    is_dark = self.theme_manager and self.theme_manager.current_theme == 'dark'
                    item_widget.update_button_style(is_dark)
                    
                    # Connect remove button - use closure to capture the widget
                    def create_remove_handler(widget):
                        def handler():
                            # Find the index by iterating through list
                            for i in range(self.file_list_widget.count()):
                                if self.file_list_widget.itemWidget(self.file_list_widget.item(i)) == widget:
                                    self.remove_file_by_index(i)
                                    break
                        return handler
                    
                    item_widget.remove_clicked.connect(create_remove_handler(item_widget))
                    
                    # Global clear when clicking an item
                    item_widget.status_clicked.connect(self.clear_all_statuses)
                    
                    # Set size and add to list
                    item.setSizeHint(item_widget.sizeHint())
                    self.file_list_widget.addItem(item)
                    self.file_list_widget.setItemWidget(item, item_widget)
                else:
                    unsupported_count += 1
        
        # Show single consolidated toast if there were unsupported files
        if unsupported_count > 0:
            self.show_unsupported_files_toast(unsupported_count)
                    
        if added_files:
            self.files_added.emit(added_files)
            self.update_placeholder_text()
            
    def get_file_size(self, file_path):
        """Get human readable file size"""
        try:
            size = os.path.getsize(file_path)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except:
            return "Unknown size"
        
    def is_supported_file(self, extension):
        """Check if file extension is supported"""
        for category, extensions in self.SUPPORTED_EXTENSIONS.items():
            if extension in extensions:
                return True
        return False
        
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
        """Update placeholder - show centered red container when empty"""
        if len(self.file_list) == 0:
            # Don't show placeholder when in PRESETS view mode (gallery is open)
            if self._current_view_mode == ViewMode.PRESETS:
                self.file_list_widget.clear()
                return
            
            # Clear all items first to avoid duplicates
            self.file_list_widget.clear()
            
            # Create a transparent wrapper
            wrapper = QWidget()
            wrapper.setStyleSheet("background-color: transparent; border: none;")
            wrapper_layout = QVBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            # Align center vertically, but let it stretch horizontally
            wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            
            # Create small centered container with transparent background
            container = QWidget()
            # Remove fixed size to adapt to width
            from PyQt6.QtWidgets import QSizePolicy
            container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            container.setStyleSheet("background-color: transparent;")
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Load SVG icon with grey color
            svg_label = QLabel()
            svg_label.setStyleSheet("background-color: transparent;")
            svg_path = Path(__file__).parent.parent / "assets" / "icons" / "drag_drop.svg"
            if svg_path.exists():
                # Apply grey color effect to the icon
                from PyQt6.QtGui import QPainter, QColor
                from PyQt6.QtWidgets import QGraphicsColorizeEffect
                
                pixmap = QPixmap(str(svg_path))
                # Scale to fit container
                pixmap = pixmap.scaledToWidth(150, Qt.TransformationMode.SmoothTransformation)
                svg_label.setPixmap(pixmap)
                
                # Apply grey colorize effect
                colorize_effect = QGraphicsColorizeEffect()
                colorize_effect.setColor(QColor(128, 128, 128))  # Grey color
                colorize_effect.setStrength(1.0)
                svg_label.setGraphicsEffect(colorize_effect)
            
            svg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(svg_label, alignment=Qt.AlignmentFlag.AlignCenter)
            
            # Add text label below the icon
            text_label = QLabel("drag and drop media files here")
            text_label.setStyleSheet("""
                background-color: transparent;
                color: #888888;
                font-size: 14px;
                padding-top: 10px;
            """)
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignCenter)
            
            wrapper_layout.addWidget(container)
            
            # Get current style and completely override item styling
            if self.theme_manager:
                styles = self.theme_manager.get_drag_drop_styles()
                base_style = styles['normal']
            else:
                base_style = ""
            
            # Replace ALL item styling to be transparent with no borders/padding
            modified_style = base_style.replace(
                'background-color: #3c3c3c;', 
                'background-color: transparent;'
            ).replace(
                'background-color: white;',
                'background-color: transparent;'
            ).replace(
                'border: 1px solid #444;',
                'border: none;'
            ).replace(
                'border: 1px solid #ddd;',
                'border: none;'
            ).replace(
                'margin: 2px;',
                'margin: 0px;'
            ).replace(
                'padding: 8px;',
                'padding: 0px;'
            )
            # Add scrollbar styling
            modified_style += self._get_scrollbar_style()
            # Also override padding and hover state to strip Theme Factory defaults
            # START RESTORATION: User wants dashed line back, but NO padding (thick outline) and NO grey bg
            modified_style += f"""
                QListWidget {{
                    border: 6px dashed {Theme.border()};
                    border-radius: {Theme.RADIUS_LG}px;
                    padding: 0px;
                    background-color: transparent;
                }}
                QListWidget:hover {{
                    border-color: {Theme.border_focus()};
                    background-color: transparent;
                }}
            """
            self.file_list_widget.setStyleSheet(modified_style)
            
            # Add wrapper to list widget with full vertical height
            item = QListWidgetItem()
            # Use a large enough size to fill the area
            viewport_size = self.file_list_widget.viewport().size()
            if viewport_size.height() < 100:  # If not properly sized yet
                item.setSizeHint(self.file_list_widget.size())
            else:
                item.setSizeHint(viewport_size)
            item.setBackground(Qt.GlobalColor.transparent)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            # Mark as placeholder with special data
            item.setData(Qt.ItemDataRole.UserRole, "PLACEHOLDER")
            self.file_list_widget.addItem(item)
            self.file_list_widget.setItemWidget(item, wrapper)
            
            self.file_list_widget.setItemWidget(item, wrapper)
            
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
        """Show a large, centered toast for insufficient credits."""
        from client.gui.components.toast_notification import ToastNotification
        
        # Dismiss any existing toast
        if hasattr(self, '_active_toast') and self._active_toast:
            try:
                self._active_toast.deleteLater()
            except RuntimeError:
                pass
                
        message = "<b>Insufficient Credits</b><br>Please recharge to continue."
        
        self._active_toast = ToastNotification(
            message=message,
            icon_type="warning",
            duration=4000,
            parent=self,
            position="center",
            size="large"
        )
        self._active_toast.dismissed.connect(lambda: setattr(self, '_active_toast', None))
        self._active_toast.show_toast()

    def show_unsupported_files_toast(self, count):
        """Show a toast notification for unsupported files"""
        from client.gui.components.toast_notification import ToastNotification
        
        # Dismiss any existing toast
        if hasattr(self, '_active_toast') and self._active_toast:
            try:
                self._active_toast.deleteLater()
            except RuntimeError:
                pass
        
        # Create and show new toast
        message = f"{count} unsupported file(s) skipped"
        self._active_toast = ToastNotification(
            message=message,
            icon_type="warning",
            duration=4000,
            parent=self
        )
        
        # Clean up reference when dismissed
        self._active_toast.dismissed.connect(lambda: setattr(self, '_active_toast', None))
        
        self._active_toast.show_toast()

    def show_conversion_toast(self, successful: int, failed: int, skipped: int, stopped: int):
        """
        Show conversion results in a toast notification with color-coded details.
        Replaces the old modal dialog.
        """
        from client.gui.components.toast_notification import ToastNotification
        
        # Colors matching the app theme
        app_green = Theme.success()
        app_yellow = Theme.warning()
        app_red = Theme.error()
        
        parts = []
        # Concise status messages
        if successful > 0:
            parts.append(f"<span style='color: {app_green};'><b>{successful}</b> exported</span>")
        
        if skipped > 0:
            parts.append(f"<span style='color: {app_yellow};'><b>{skipped}</b> skipped</span>")
            
        if failed > 0:
            parts.append(f"<span style='color: {app_red};'><b>{failed}</b> failed</span>")
            
        if stopped > 0:
            parts.append(f"<span style='color: {app_yellow};'><b>{stopped}</b> stopped</span>")
            
        if not parts:
            parts.append("No files processed")
            
        # Join with line breaks
        message = "<br>".join(parts)
        
        # Determine icon type
        if failed > 0:
            icon = "error"
        elif stopped > 0 or skipped > 0:
            icon = "warning"
        else:
            icon = "info"
            
        # Dismiss any existing toast
        if hasattr(self, '_active_toast') and self._active_toast:
            try:
                self._active_toast.deleteLater()
            except RuntimeError:
                pass
                
        # Show toast with slightly longer duration for results
        self._active_toast = ToastNotification(
            message=message,
            icon_type=icon,
            duration=5000, 
            parent=self,
            position="bottom-right"
        )
        self._active_toast.dismissed.connect(lambda: setattr(self, '_active_toast', None))
        self._active_toast.show_toast()
            
    def handle_list_key_press(self, event):
        """Handle keyboard events for the file list"""
        from PyQt6.QtCore import Qt
        
        # Handle Delete and Backspace keys to remove selected items
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected_items = self.file_list_widget.selectedItems()
            if selected_items:
                # Remove items in reverse order to maintain correct indices
                for item in reversed(selected_items):
                    if not item.text().startswith("[FILE]"):  # Don't remove placeholder
                        row = self.file_list_widget.row(item)
                        file_path = self.file_list[row]
                        
                        # Remove from both lists
                        self.file_list.remove(file_path)
                        self.file_list_widget.takeItem(row)
                
                # Update placeholder if empty
                self.update_placeholder_text()
        else:
            # Call the original key press event handler for other keys
            QListWidget.keyPressEvent(self.file_list_widget, event)
            
    def show_context_menu(self, position):
        """Show context menu for file operations"""
        item = self.file_list_widget.itemAt(position)
        
        # Only show for actual files (not placeholder)
        if item and item.data(Qt.ItemDataRole.UserRole) != "PLACEHOLDER":
            from PyQt6.QtWidgets import QMenu
            
            menu = QMenu(self)
            remove_action = menu.addAction("Remove File")
            show_action = menu.addAction("Show in Explorer")
            
            # Themed styling
            is_dark = self.theme_manager and self.theme_manager.current_theme == 'dark'
            Theme.set_dark_mode(is_dark)
            
            # CSS with first-child (red) and last-child (blue)
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {Theme.surface_element()};
                    color: {Theme.text()};
                    border: 1px solid {Theme.border()};
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 4px;
                }}
                QMenu::item {{
                    padding: 6px 24px;
                    border-radius: {Theme.RADIUS_SM}px;
                }}
                QMenu::item:selected {{
                    background-color: #666666;
                    color: white;
                }}
            """)
            
            action = menu.exec(self.file_list_widget.mapToGlobal(position))
            if action == remove_action:
                self.remove_file_item(item)
            elif action == show_action:
                self.show_in_explorer(item)
            
    def show_in_explorer(self, item):
        """Open file location in Windows Explorer and select the file"""
        if item and item.data(Qt.ItemDataRole.UserRole) != "PLACEHOLDER":
            row = self.file_list_widget.row(item)
            if 0 <= row < len(self.file_list):
                file_path = self.file_list[row]
                
                import subprocess
                try:
                    # Verify file exists
                    if not os.path.exists(file_path):
                        print(f"File not found: {file_path}")
                        return
                    
                    # Normalize path for Windows
                    normalized_path = os.path.normpath(file_path)
                    
                    # Open Explorer and select the file in a new window
                    # The /select, parameter highlights the file
                    subprocess.Popen(['explorer', '/select,', normalized_path])
                    print(f"Opened Explorer for: {normalized_path}")
                    
                except Exception as e:
                    print(f"Error opening Explorer: {e}")
                    # Fallback: just open the folder
                    try:
                        folder_path = os.path.dirname(file_path)
                        if os.path.exists(folder_path):
                            subprocess.Popen(['explorer', os.path.normpath(folder_path)])
                    except Exception as e2:
                        print(f"Error opening folder: {e2}")
            


    def get_files(self):
        """Return the list of selected files"""
        return self.file_list.copy()


