"""
Main Window for Graphics Conversion App
Implements the layout: Top Bar | Mid Section (Drag-Drop + Commands) | Bottom Bar
"""

import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QDialog, QApplication,
    QGraphicsDropShadowEffect, QSplitter, QTextEdit, QProgressBar,
    QStatusBar
)
from PyQt6.QtGui import QIcon, QFont, QAction, QColor
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, pyqtSlot, QTimer

from .drag_drop_area import DragDropArea
from .command_panel import CommandPanel
from .output_footer import OutputFooter
from .theme_manager import ThemeManager
from .title_bar import TitleBarWindow
from client.core.conversion_engine import ConversionEngine, ToolChecker
from client.gui.custom_widgets import PresetStatusButton
from client.utils.trial_manager import TrialManager
from client.utils.font_manager import AppFonts, FONT_FAMILY_APP_NAME
from client.utils.resource_path import get_app_icon_path, get_resource_path
from client.version import APP_NAME, AUTHOR


# Mediator-Shell Architecture Components
from client.gui.animators.side_panel_animator import SidePanelAnimator
from client.gui.components.control_bar import ControlBar
from client.gui.components.status_panel import StatusPanel
from client.gui.utils.window_behavior import FramelessWindowBehavior
from client.gui.utils.dev_tools import EventDebugFilter, DEBUG_INTERACTIVITY
from client.gui.utils.dialog_manager import DialogManager
from client.gui.drag_drop_area import ViewMode
from client.utils.session_manager import SessionManager
from enum import Enum


class Mode(Enum):
    """Application mode for MainWindow conductor."""
    PRESET = "preset"  # Preset mode - simple drag & drop with presets
    LAB = "lab"        # Lab mode - full command panel visible


class MainWindow(QMainWindow):
    def __init__(self, is_trial=False):
        super().__init__()
        
        # Install interactive debugger
        if DEBUG_INTERACTIVITY:
            self._debug_filter = EventDebugFilter()
            QApplication.instance().installEventFilter(self._debug_filter)
            print("[DEBUG] Interactive Debug Filter Installed")
            
        self.is_trial = is_trial
        
        # Development mode detection
        self.DEVELOPMENT_MODE = getattr(sys, '_called_from_test', False) or __debug__ and not getattr(sys, 'frozen', False)
        
        title = APP_NAME
        if self.is_trial:
            title += " [TRIAL]"  # Shortened for title bar consistency
        if self.DEVELOPMENT_MODE:
            title += " [DEV]"
            
        self.setWindowTitle(title)
        
        # Make window frameless for custom title bar & transparent for rounded corners
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True) # Ensure window accepts drops for the overlay logic
            
        self.setGeometry(100, 100, 1200, 1000)
        self.setMinimumSize(800, 700)
        self.setMouseTracking(True)  # Enable mouse tracking for edge resize cursors
        
        if self.is_trial:
            self.trial_manager = TrialManager()
            # Auto-reset trial in development mode
            if self.DEVELOPMENT_MODE:
                print("[DEV] Resetting trial usage...")
                self.trial_manager.reset_trial_usage()
        
        # Set window icon if available
        try:
            from PyQt6.QtGui import QIcon
            from client.utils.resource_path import get_app_icon_path
            
            icon_path = get_app_icon_path()
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Could not set window icon: {e}")
        
        # Conversion engine
        self.conversion_engine = None
        
        # Theme management (Singleton pattern)
        self.theme_manager = ThemeManager.instance()
        
        # Dialog management (Mediator-Shell: centralized dialogs)
        self.dialogs = DialogManager(self, self.theme_manager)
        
        # Track mouse position for window dragging
        self.drag_position = None
        
        # Mediator-Shell: Mode tracking
        self._current_mode = Mode.PRESET  # Default to preset mode
        self._active_lab_tab = 0          # Track active lab tab (0=Image, 1=Video, 2=Loop)
        
        # Mediator-Shell: Window behavior (resize, blur)
        self.window_behavior = FramelessWindowBehavior(self, border_width=8)
        
        self.setup_ui()
        self.setup_status_bar()
        self.connect_signals()
        
        # Connect to theme changes and apply initial theme
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed(self.theme_manager.is_dark_mode())
        
        self.check_tools()
        
        # Reset drop area rendering after 1ms
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1, self.drag_drop_area.clear_files)
        
    def setup_ui(self):
        """Setup the main user interface layout"""
        central_widget = QWidget()
        central_widget.setMouseTracking(True)
        self.setCentralWidget(central_widget)
        
        # Main vertical layout (No margins - direct window edge)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        
        # Root Frame (The visible container)
        self.root_frame = QFrame()
        self.root_frame.setMouseTracking(True)
        self.root_frame.setObjectName("RootFrame")
        # No shadow effect - clean window edges
        
        main_layout.addWidget(self.root_frame)
        
        # Root Layout inside the frame
        root_layout = QVBoxLayout(self.root_frame)
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create SEPARATE title bar window (with blur)
        # Parent=self ensures z-order follows main window
        self.title_bar_window = TitleBarWindow(
            parent=self,
            is_trial=self.is_trial,
            is_dev_mode=self.DEVELOPMENT_MODE
        )
        self._connect_title_bar_signals()
        QApplication.processEvents()
        
        # Content area container (opaque) - now the only content in root_frame
        self.content_container = QFrame()
        self.content_container.setObjectName("ContentFrame")
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setSpacing(5)
        content_layout.setContentsMargins(5, 0, 5, 5)  # No top margin to avoid gap with title bar
        
        # Create unified control bar (File Buttons | Preset | Lab)
        self.create_control_bar(content_layout)
        
        # Create the middle section with splitter
        self.create_middle_section(content_layout)
        
        # Bottom section (status and progress)
        self.create_bottom_section(content_layout)
        
        # Create output footer
        self.output_footer = OutputFooter()
        self.output_footer.start_conversion.connect(self._on_footer_start)
        self.output_footer.stop_conversion.connect(self.stop_conversion)
        content_layout.addWidget(self.output_footer)
        
        # Add content container to root layout
        root_layout.addWidget(self.content_container)

        # Note: Preset overlay is now inside DragDropArea
        
        # Process events to keep splash screen animated
        QApplication.processEvents()
    
    def _connect_title_bar_signals(self):
        """Wire up TitleBarWindow signals to main window methods"""
        self.title_bar_window.minimize_requested.connect(self.showMinimized)
        self.title_bar_window.close_requested.connect(self.close)
        self.title_bar_window.theme_toggle_requested.connect(self.toggle_theme)
        self.title_bar_window.show_advanced_requested.connect(self.show_advanced)
        self.title_bar_window.show_about_requested.connect(self.show_about)
        self.title_bar_window.logout_requested.connect(self.logout)

    
    def create_control_bar(self, parent_layout):
        """Create the unified control bar using the ControlBar component."""
        # Create the ControlBar component (Mediator-Shell Pattern)
        self.control_bar = ControlBar()
        
        # Connect signals to MainWindow handlers (Mediator routing)
        self.control_bar.preset_mode_clicked.connect(self._on_preset_btn_clicked)
        self.control_bar.lab_mode_clicked.connect(self._on_lab_item_clicked)
        
        # Expose child references for backward compatibility
        self.add_files_btn = self.control_bar.add_files_btn
        self.add_folder_btn = self.control_bar.add_folder_btn
        self.clear_files_btn = self.control_bar.clear_files_btn
        self.preset_status_btn = self.control_bar.preset_status_btn
        self.lab_btn = self.control_bar.lab_btn
        
        parent_layout.addWidget(self.control_bar)
    
    # =========================================================================
    # MEDIATOR-SHELL: MODE CONDUCTOR
    # =========================================================================
    # Centralized mode switching logic. All mode changes go through switch_mode()
    # to ensure consistent state across all components.
    # =========================================================================
    
    @property
    def current_mode(self) -> Mode:
        """Get the current application mode."""
        return self._current_mode
    
    def switch_mode(self, mode: Mode, lab_tab: int = None):
        """
        Centralized mode switching - the heart of the Mediator pattern.
        
        All mode changes should go through this method to ensure:
        1. Consistent state across all components
        2. Proper animation sequencing
        3. UI state synchronization
        
        Args:
            mode: Target mode (Mode.PRESET or Mode.LAB)
            lab_tab: For LAB mode, which tab to activate (0=Image, 1=Video, 2=Loop)
        """
        if mode == Mode.PRESET:
            self._enter_preset_mode()
        elif mode == Mode.LAB:
            self._enter_lab_mode(lab_tab if lab_tab is not None else self._active_lab_tab)
        
        self._current_mode = mode
        self._update_footer_mode_active()

    def _update_footer_mode_active(self):
        """Update output footer mode active state based on current app state"""
        if hasattr(self, 'output_footer'):
            is_lab = (self._current_mode == Mode.LAB)
            has_preset = (hasattr(self, '_active_preset') and self._active_preset is not None)
            self.output_footer.set_mode_active(is_lab or has_preset)
    
    def _enter_preset_mode(self):
        """Internal: Configure UI for Preset mode."""
        # 1. Hide Command Panel
        self.panel_animator.close()
        
        # 2. Deactivate Lab Button (Ghost style)
        if hasattr(self, 'lab_btn'):
            self.lab_btn.set_style_solid(False)
            self.lab_btn.set_main_icon("client/assets/icons/lab_icon.svg")
        
        # 3. Notify CommandPanel state
        if hasattr(self, 'command_panel'):
            self.command_panel.set_lab_mode_active(False)
            self.command_panel.set_top_bar_preset_mode(True)
        
        # 4. Show Preset Overlay AFTER panel animation completes
        # Delay to allow drop area to expand to full width first
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(350, self._show_preset_gallery_delayed)
    
    def _show_preset_gallery_delayed(self):
        """Show preset gallery after panel animation delay."""
        if hasattr(self, 'drag_drop_area'):
            self.drag_drop_area.set_view_mode(ViewMode.PRESETS)
    
    def _toggle_preset_gallery(self):
        """
        Toggle the preset gallery overlay visibility without changing modes.
        
        This is called when the user clicks the preset button while already
        in Preset mode. Closing the gallery doesn't exit Preset mode - only
        selecting a Lab option does that.
        """
        if not hasattr(self, 'drag_drop_area'):
            return
        
        current_view = self.drag_drop_area.current_view_mode
        
        if current_view == ViewMode.PRESETS:
            # Gallery is open - close it (but stay in Preset mode)
            self.drag_drop_area.set_view_mode(ViewMode.FILES)
        else:
            # Gallery is closed - open it
            self.drag_drop_area.set_view_mode(ViewMode.PRESETS)
    
    def _enter_lab_mode(self, lab_tab: int):
        """Internal: Configure UI for Lab mode."""
        # Icon paths matching tab order
        icons = [
            "client/assets/icons/pic_icon2.svg",
            "client/assets/icons/vid_icon.svg",
            "client/assets/icons/loop_icon3.svg"
        ]
        
        # 1. Update lab button appearance
        if 0 <= lab_tab < len(icons):
            self.lab_btn.set_main_icon(icons[lab_tab])
            self.lab_btn.set_style_solid(True)
        
        # 2. Reset Preset button to default state
        if hasattr(self, 'preset_status_btn'):
            self.preset_status_btn.set_active(False)
        
        # 3. Notify CommandPanel
        if hasattr(self, 'command_panel'):
            self.command_panel.set_lab_mode_active(True)
            self.command_panel.set_top_bar_preset_mode(False)
            self.command_panel._on_tab_btn_clicked(lab_tab)
        
        # 4. Hide Preset Overlay
        if hasattr(self, 'drag_drop_area'):
            self.drag_drop_area.set_view_mode(ViewMode.FILES)
        
        # 5. Animate panel
        panel_already_visible = self.right_frame.isVisible()
        if not panel_already_visible:
            self.panel_animator.trigger_side_buttons_animation(hide=True)
        self.panel_animator.open()
        
        # 6. Track active tab
        self._active_lab_tab = lab_tab
    
    # =========================================================================
    # BUTTON HANDLERS (Now delegate to switch_mode)
    # =========================================================================
    
    def _on_preset_btn_clicked(self):
        """
        Handle preset button click.
        
        Behavior:
        - If currently in LAB mode: Switch to PRESET mode (opens gallery)
        - If currently in PRESET mode: Toggle gallery visibility only
          (keeps Preset Mode ON until Lab option is selected)
        """
        if self._current_mode == Mode.LAB:
            # Switch from Lab to Preset mode
            self.switch_mode(Mode.PRESET)
        else:
            # Already in Preset mode - just toggle the gallery visibility
            self._toggle_preset_gallery()
    
    def _on_lab_item_clicked(self, item_id):
        """Handle lab button menu item click - delegate to switch_mode()."""
        type_map = {0: "IMAGE", 1: "VIDEO", 2: "LOOP"}
        print(f"[DEBUG_MAIN] Lab item clicked. ID={item_id} ({type_map.get(item_id, 'UNKNOWN')})")
        self.switch_mode(Mode.LAB, lab_tab=item_id)
        
    def create_middle_section(self, parent_layout):
        """Create the split middle section with drag-drop and command areas"""
        # Create horizontal splitter for left and right panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)  # Hide splitter handle visual
        splitter.setStyleSheet("QSplitter::handle { background: transparent; border: none; }")
        
        # Store splitter reference for styling
        self.splitter = splitter
        
        # Left panel - Drag and Drop Area (no frame)
        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        self.drag_drop_area = DragDropArea()
        left_layout.addWidget(self.drag_drop_area)
        
        # Right panel - Command Panel (no frame)
        right_frame = QWidget()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        self.command_panel = CommandPanel()
        self.command_panel.setMinimumWidth(0) # Ensure it can animate from 0
        right_layout.addWidget(self.command_panel)
        
        # Store right frame reference for toggling
        self.right_frame = right_frame
        self.right_frame.setMinimumWidth(0) # Ensure frame can animate from 0
        self.right_frame.setVisible(False)  # Hidden on init
        
        # Add panels to splitter
        splitter.addWidget(left_frame)
        splitter.addWidget(right_frame)
        
        # Set initial sizes (100% left, 0% right)
        # Note: Since right_frame is hidden, sizes might be ignored, but good to set
        splitter.setSizes([1200, 0])
        
        parent_layout.addWidget(splitter)
        
        # Initialize SidePanelAnimator (Mediator-Shell Pattern)
        self.panel_animator = SidePanelAnimator(
            splitter=self.splitter,
            command_panel=self.command_panel,
            right_frame=self.right_frame
        )
        # Wire up button animation callbacks - animator now handles these internally
        self.panel_animator.set_button_callbacks(
            on_show=lambda: self.panel_animator.trigger_side_buttons_animation(hide=False),
            on_hide=lambda: self.panel_animator.trigger_side_buttons_animation(hide=True)
        )

    # =========================================================================
    # COMMAND PANEL SLIDE ANIMATION (Delegated to SidePanelAnimator)
    # =========================================================================
    # Animation configuration is now managed by:
    #   client/gui/animators/side_panel_animator.py
    # 
    # The SidePanelAnimator is initialized in create_middle_section() and
    # provides: open(), close(), toggle() methods.
    # =========================================================================
        
    def create_bottom_section(self, parent_layout):
        """Create the bottom section with status and progress"""
        bottom_frame = QFrame()
        bottom_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        bottom_frame.setMaximumHeight(100)
        bottom_frame.setVisible(False)  # Hide by default
        
        bottom_layout = QVBoxLayout(bottom_frame)
        
        # Status text area
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(60)
        self.status_text.setReadOnly(True)
        self.status_text.setPlainText("Ready to convert graphics files...")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        bottom_layout.addWidget(QLabel("Status:"))
        bottom_layout.addWidget(self.status_text)
        bottom_layout.addWidget(self.progress_bar)
        
        parent_layout.addWidget(bottom_frame)
        
        # Store reference to bottom frame for toggling
        self.bottom_frame = bottom_frame
        
    def setup_menu_bar(self):
        """Hide the menu bar completely"""
        menubar = self.menuBar()
        menubar.hide()
        
    def setup_status_bar(self):
        """Setup the bottom status bar using StatusPanel component."""
        # Create the StatusPanel component (Mediator-Shell Pattern)
        self.status_panel = StatusPanel()
        
        # Expose child references for backward compatibility
        self.progress_container = self.status_panel
        self.file_progress_bar = self.status_panel.file_progress_bar
        self.total_progress_bar = self.status_panel.total_progress_bar
        self._completed_files_count = 0
        
        # Add progress bar to the central widget's layout
        if self.centralWidget():
            central_layout = self.centralWidget().layout()
            if central_layout:
                central_layout.addWidget(self.status_panel)
        
        # Status bar - hidden (no resize grip shown)
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.setStatusBar(self.status_bar)
        self.status_bar.hide()
        
    def update_status(self, message):
        """Update status in both status bar and status text area"""
        self.status_bar.showMessage(message)
        self.status_text.append(f"[INFO] {message}")
        
        # Auto-scroll to bottom
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.status_text.setTextCursor(cursor)
        
    def show_progress(self, visible=True):
        """Show or hide the progress bar"""
        self.progress_bar.setVisible(visible)
        
    def set_progress(self, value):
        """Set progress bar value (0-100)"""
        self.progress_bar.setValue(value)
    
    @pyqtSlot(int, float)
    def on_file_progress(self, file_index, progress):
        """Handle individual file progress update"""
        # Update file list item progress
        self.drag_drop_area.set_file_progress(file_index, progress)
        
        # Update separated progress bars
        if hasattr(self, 'file_progress_bar'):
            self.file_progress_bar.set_progress(progress)
            
        if hasattr(self, 'total_progress_bar'):
            # Calculate total progress
            total_files = len(self.drag_drop_area.file_list)
            if total_files > 0:
                # Base progress from completed files
                base_progress = self._completed_files_count / total_files
                # Add fraction of current file
                current_fraction = progress / total_files
                self.total_progress_bar.set_progress(base_progress + current_fraction)
        
    def connect_signals(self):
        """Connect signals between components"""
        # Connect drag-drop area signals
        self.drag_drop_area.files_added.connect(self.on_files_added)
        self.drag_drop_area.preset_applied.connect(self.on_preset_applied)
        
        # Connect drag-drop area status updates to main window
        self.drag_drop_area.update_status = self.update_status
        
        # Connect command panel signals
        self.command_panel.conversion_requested.connect(self.start_conversion)
        self.command_panel.stop_conversion_requested.connect(self.stop_conversion)
        self.command_panel.global_mode_changed.connect(self.on_mode_changed)
        self.command_panel.lab_state_changed.connect(self._on_lab_state_changed)
        
        # Propagate dev mode to command panel (enables estimator version selector)
        self.command_panel.set_dev_mode(self.DEVELOPMENT_MODE)
        
        # Connect unified control bar buttons to drag-drop area
        self.add_files_btn.clicked.connect(self.drag_drop_area.add_files_dialog)
        self.add_folder_btn.clicked.connect(self.drag_drop_area.add_folder_dialog)
        self.clear_files_btn.clicked.connect(self.drag_drop_area.clear_files)
    
    def _on_lab_state_changed(self, icon_path, is_solid):
        """Handle lab button state change from CommandPanel"""
        if hasattr(self, 'lab_btn'):
            self.lab_btn.set_main_icon(icon_path)
            self.lab_btn.set_style_solid(is_solid)
        
    def on_files_added(self, files):
        """Handle files added to drag-drop area"""
        self.update_status(f"Added {len(files)} file(s)")
        # Update footer visibility
        if hasattr(self, 'output_footer'):
            has_files = len(self.drag_drop_area.get_files()) > 0
            self.output_footer.set_has_files(has_files)
            
        # USER REQUEST: "After dragging the file the PRESET view is on"
        # Manually trigger the preset view when new files are added
        self.drag_drop_area.show_preset_view()
    
    def _on_footer_start(self):
        """Handle start button click from output footer"""
        # Check if preset mode is active
        if hasattr(self, '_active_preset') and self._active_preset is not None:
            self._start_preset_conversion()
            return
        
        # Normal conversion path - get complete payload from command panel
        params = self.command_panel.get_execution_payload()
        
        # Override output settings from footer
        output_mode = self.output_footer.get_output_mode()
        if output_mode == "source":
            params['output_same_folder'] = True
            params['use_nested_output'] = False  # Fixed: was 'output_nested'
            params['output_custom'] = False
        elif output_mode == "organized":
            params['output_same_folder'] = False
            params['use_nested_output'] = True  # Fixed: was 'output_nested'
            params['nested_output_name'] = self.output_footer.get_organized_name()  # Fixed: was 'nested_folder_name'
            params['output_custom'] = False
        elif output_mode == "custom":
            params['output_same_folder'] = False
            params['use_nested_output'] = False  # Fixed: was 'output_nested'
            params['output_custom'] = True
            params['output_dir'] = self.output_footer.get_custom_path()
        
        self.start_conversion(params)
    
    def _start_preset_conversion(self):
        """
        Execute conversion using the active preset - delegates to PresetOrchestrator.
        
        MainWindow acts as a Conductor here: it collects parameters from UI components
        and routes the request to the orchestrator, which handles all business logic.
        """
        files = self.drag_drop_area.get_files()
        if not files:
            self.dialogs.show_warning("No Files", "Please add files for conversion first.")
            return
        
        # Get orchestrator (owns the conversion logic)
        if not hasattr(self.drag_drop_area, '_preset_orchestrator'):
            self.dialogs.show_error("Error", "Preset orchestrator not available.")
            return
        
        orchestrator = self.drag_drop_area._preset_orchestrator
        
        # Collect output settings from footer (UI -> Data)
        output_mode = self.output_footer.get_output_mode()
        organized_name = self.output_footer.get_organized_name() or "output"
        custom_path = self.output_footer.get_custom_path()
        
        # Update UI state (show converting)
        if hasattr(self, 'output_footer'):
            self.output_footer.set_converting(True)
        self.show_progress(True)
        
        preset_name = self._active_preset.name if self._active_preset else "Unknown"
        self.update_status(f"Converting with preset: {preset_name}")
        
        # Wire up progress signals from orchestrator
        def on_progress(current, total, message):
            progress = int(current / total * 100) if total > 0 else 0
            self.set_progress(progress)
            self.update_status(message)
        
        def on_finished(success, message):
            self.set_progress(100)
            self.update_status(message)
            if hasattr(self, 'output_footer'):
                self.output_footer.set_converting(False)
            self.show_progress(False)
            self.dialogs.show_completion(success, message)
        
        # Connect signals (disconnect after use to prevent stacking)
        orchestrator.conversion_progress.connect(on_progress)
        orchestrator.conversion_finished.connect(on_finished)
        
        # Delegate execution to orchestrator (Strategy Pattern)
        orchestrator.run_conversion(
            files=files,
            output_mode=output_mode,
            organized_name=organized_name,
            custom_path=custom_path
        )
        
        # Disconnect signals after execution
        try:
            orchestrator.conversion_progress.disconnect(on_progress)
            orchestrator.conversion_finished.disconnect(on_finished)
        except TypeError:
            pass  # Already disconnected


        

    def start_conversion(self, params):
        """
        Start the conversion process.
        
        MainWindow acts as a Conductor: it validates preconditions, then
        delegates to ConversionEngine. Parameter gathering is done by CommandPanel.
        """
        files = self.drag_drop_area.get_files()
        
        if not files:
            self.dialogs.show_warning("No Files", "Please add files for conversion first.")
            return
            
        if self.conversion_engine and self.conversion_engine.isRunning():
            self.dialogs.show_warning("Conversion Running", "A conversion is already in progress.")
            return
        
        # Update UI state
        if hasattr(self, 'output_footer'):
            self.output_footer.set_converting(True)
        
        # Check if we should use TargetSizeConversionEngine (v2 + max_size mode)
        use_target_size_engine = False
        size_mode = params.get('video_size_mode') or params.get('image_size_mode') or params.get('gif_size_mode')
        
        if size_mode == 'max_size':
            from client.core.size_estimator_registry import get_estimator_version
            if get_estimator_version() == 'v2':
                use_target_size_engine = True
                print("[MainWindow] Using TargetSizeConversionEngine (v2 active)")
        
        # Create appropriate engine
        if use_target_size_engine:
            from client.core.target_size_conversion_engine import TargetSizeConversionEngine
            self.conversion_engine = TargetSizeConversionEngine(files, params)
        else:
            self.conversion_engine = ConversionEngine(files, params)
        
        # Connect engine signals
        self.conversion_engine.progress_updated.connect(self.set_progress)
        self.conversion_engine.file_progress_updated.connect(self.on_file_progress)
        self.conversion_engine.status_updated.connect(self.update_status)
        self.conversion_engine.file_completed.connect(self.on_file_completed)
        
        # Handle different signal names between engines
        if hasattr(self.conversion_engine, 'conversion_finished'):
            self.conversion_engine.conversion_finished.connect(self.on_conversion_finished)
        elif hasattr(self.conversion_engine, 'conversion_completed'):
            self.conversion_engine.conversion_completed.connect(
                lambda s, f: self.on_conversion_finished(s > 0, f"Completed: {s} success, {f} failed")
            )
        
        # Reset progress bars
        if hasattr(self, 'file_progress_bar'):
            self.file_progress_bar.set_progress(0)
        if hasattr(self, 'total_progress_bar'):
            self.total_progress_bar.set_progress(0)
            
        # Start conversion
        self.show_progress(True)
        self.set_progress(0)
        self.update_status("Starting conversion...")
        self.conversion_engine.start()
    
    def stop_conversion(self):
        """Stop the current conversion process"""
        if self.conversion_engine and self.conversion_engine.isRunning():
            self.update_status("Stopping conversion...")
            self.conversion_engine.stop_conversion()
            # The button state will be reset in on_conversion_finished
    
    @pyqtSlot(int, float)
    def on_file_progress(self, file_index, progress):
        """Handle individual file progress update"""
        self.drag_drop_area.set_file_progress(file_index, progress)
        if hasattr(self, 'file_progress_bar'):
            self.file_progress_bar.set_progress(progress, animate=True, min_duration_ms=500)
    
    def on_file_completed(self, source_file, output_file):
        """Handle completed file conversion"""
        import os
        source_name = os.path.basename(source_file)
        output_name = os.path.basename(output_file)
        self.update_status(f"✓ Converted: {source_name} → {output_name}")
        
        # Ensure blue bar reaches 100% for this file
        if hasattr(self, 'file_progress_bar'):
            self.file_progress_bar.set_progress(1.0, animate=True, min_duration_ms=500)
        
        # Mark the file as completed in the list
        # Find the file index
        for i, f in enumerate(self.drag_drop_area.file_list):
            if f == source_file:
                self.drag_drop_area.set_file_completed(i)
                self._completed_files_count += 1
                # Update total progress bar
                if hasattr(self, 'total_progress_bar'):
                    total_files = len(self.drag_drop_area.file_list)
                    if total_files > 0:
                        self.total_progress_bar.set_progress(self._completed_files_count / total_files)
                break
        
    def on_conversion_finished(self, success, message):
        """Handle conversion completion"""
        # Reset button state (handled by footer)
        # Reset footer state
        if hasattr(self, 'output_footer'):
            self.output_footer.set_converting(False)
        
        self.show_progress(False)
        self.set_progress(0)
        
        # Reset separated progress bars
        if hasattr(self, 'file_progress_bar'):
            self.file_progress_bar.set_progress(0)
        if hasattr(self, 'total_progress_bar'):
            self.total_progress_bar.set_progress(0)
        
        self._completed_files_count = 0
        
        self.update_status(message)
        
        self.dialogs.show_completion(success, message)
            
    def check_tools(self):
        """Check if required tools are available"""
        tools = ToolChecker.get_tool_status()
        detailed_status = ToolChecker.get_detailed_status()
        
        missing_tools = [tool for tool, available in tools.items() if not available]
        
        if missing_tools:
            # Create detailed message
            message_parts = ["Tool Status Check:\n"]
            for tool, status in detailed_status.items():
                icon = "✓" if tools[tool] else "✗"
                message_parts.append(f"{icon} {tool.title()}: {status}")
            
            message = "\n".join(message_parts)
            message += f"\n\nNote: The app will use fallback methods for missing tools."
            
            self.dialogs.show_tool_status(message)
        
    def _on_theme_changed(self, is_dark: bool):
        """Handle theme changes via ThemeManager signal"""
        # Apply main window styles (with caching to avoid redundant updates)
        main_style = self.theme_manager.get_main_window_style()
        
        # Only call setStyleSheet if the style actually changed
        if not hasattr(self, '_cached_main_style') or self._cached_main_style != main_style:
            self.setStyleSheet(main_style)
            self._cached_main_style = main_style
        
        # Update drag drop area theme
        self.drag_drop_area.set_theme_manager(self.theme_manager)
        
        # Update command panel theme
        if hasattr(self.command_panel, 'update_theme'):
            self.command_panel.update_theme(is_dark)
        
        # Update control bar theme
        if hasattr(self, 'control_bar'):
            self.control_bar.update_theme(is_dark)
        
        # Update title bar theme
        self.update_title_bar_theme(is_dark)
        
        # Apply global QToolTip styling
        from client.gui.custom_widgets import apply_tooltip_style
        apply_tooltip_style(is_dark)
        
        # Update output footer theme
        if hasattr(self, 'output_footer'):
            self.output_footer.update_theme(is_dark)
        
    def update_title_bar_theme(self, is_dark):
        """Update title bar colors based on theme"""
        # Delegate to the separate TitleBarWindow
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window.apply_theme(is_dark)
        
        # Content frame styling (Opaque, rounded bottom corners)
        if is_dark:
            content_bg = "#2b2b2b"
        else:
            content_bg = "#ffffff"
        
        if hasattr(self, 'content_container'):
            self.content_container.setStyleSheet(f"""
                QFrame#ContentFrame {{
                    background-color: {content_bg};
                    border-bottom-left-radius: 12px;
                    border-bottom-right-radius: 12px;
                }}
            """)

        
    def toggle_theme(self):
        """Toggle between dark and light theme"""
        current_theme = self.theme_manager.get_current_theme()
        new_theme = 'light' if current_theme == 'dark' else 'dark'
        self.theme_manager.set_theme(new_theme)
        # Note: Widgets auto-update via theme_changed signal
        # MainWindow-specific updates handled in _on_theme_changed()
        
    def toggle_status_bar(self):
        """Toggle the visibility of the status bar section"""
        if hasattr(self, 'bottom_frame'):
            is_visible = self.bottom_frame.isVisible()
            self.bottom_frame.setVisible(not is_visible)

    def show_about(self):
        """Show the About dialog"""
        from client.gui.components.about_dialog import show_about_dialog
        show_about_dialog(self, self.theme_manager)


    def show_advanced(self):
        """Show the Advanced Settings dialog"""
        from .advanced_settings_window import AdvancedSettingsWindow
        
        dialog = AdvancedSettingsWindow(parent=self, theme_manager=self.theme_manager)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            # Settings were saved, show confirmation
            self.dialogs.show_info("Settings Saved", "Advanced settings have been saved successfully.")
    
    def logout(self):
        """Logout from the application and show login window."""
        # Confirm logout first (dialog stays in MainWindow for UI control)
        if self.dialogs.confirm_action("Logout", "Are you sure you want to logout?"):
            # Delegate to SessionManager for clean logout flow
            session_mgr = SessionManager(self, lambda: self.conversion_engine)
            session_mgr.logout()
            
    def resizeEvent(self, event):
        """Handle resize event - sync title bar width"""
        super().resizeEvent(event)
        # Sync title bar width
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window._sync_width()

    def moveEvent(self, event):
        """Handle move event - sync title bar position"""
        super().moveEvent(event)
        # Sync title bar position
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window._sync_position()

    def showEvent(self, event):
        """Override showEvent - show title bar window"""
        super().showEvent(event)
        # Show and position the separate title bar window
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window.attach_to(self)
            self.title_bar_window.show()
        # NOTE: Blur is now ONLY on the title bar window, not main window
        self.enable_mouse_tracking_all()
        
    def closeEvent(self, event):
        """Close title bar window when main window closes"""
        if hasattr(self, 'title_bar_window'):
            self.title_bar_window.close()
        super().closeEvent(event)
        
    def enable_mouse_tracking_all(self):
        """Recursively enable mouse tracking for all widgets to ensure resize events propagate"""
        self.setMouseTracking(True)
        for widget in self.findChildren(QWidget):
            widget.setMouseTracking(True)
    
    def mousePressEvent(self, event):
        """Delegate window resize to FramelessWindowBehavior."""
        if self.window_behavior.handle_mouse_press(event):
            return
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        """Delegate to FramelessWindowBehavior."""
        self.window_behavior.handle_mouse_release(event)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Delegate resize and cursor updates to FramelessWindowBehavior."""
        if self.window_behavior.handle_mouse_move(event):
            return
        super().mouseMoveEvent(event)
    
    def changeEvent(self, event):
        """Handle window state changes - sync title bar visibility on minimize/restore"""
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, 'title_bar_window'):
                if self.isMinimized():
                    self.title_bar_window.hide()
                else:
                    self.title_bar_window.show()
                    self.title_bar_window._sync_position()
        # When main window is activated, also raise the title bar
        elif event.type() == event.Type.ActivationChange:
            if self.isActiveWindow() and hasattr(self, 'title_bar_window'):
                self.title_bar_window.raise_()
    
    # --- Drag & Drop - Forward to DragDropArea ---
    
    def dragEnterEvent(self, event):
        """Accept drag anywhere on window"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Accept drag move"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        """Handle drag leave"""
        super().dragLeaveEvent(event)
    
    def dropEvent(self, event):
        """Forward drop to DragDropArea"""
        if event.mimeData().hasUrls():
            files = []
            folders = []
            
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                import os
                if os.path.isfile(path):
                    files.append(path)
                elif os.path.isdir(path):
                    folders.append(path)
            
            # Collect all files including from folders
            all_files = files.copy()
            for folder in folders:
                folder_files = self.drag_drop_area.get_supported_files_from_folder(folder, True)
                all_files.extend(folder_files)
            
            # Store as pending in DragDropArea
            self.drag_drop_area._pending_files = all_files
            
            event.acceptProposedAction()
        else:
            event.ignore()
        
    # --- Preset Selection Handler ---
    
    def on_preset_applied(self, preset, files):
        """Handle preset applied from DragDropArea overlay"""
        file_count = len(files) if files else 0
        print(f"[Smart Drop] Applying preset: {preset.name} to {file_count} files")
        
        # Store active preset for conversion
        self._active_preset = preset
        
        # 1. Add files to the DragDropArea if any
        if files:
            self.drag_drop_area.add_files(files)
        
        # 2. Update UI to reflect Active Preset State
        if hasattr(self, 'preset_status_btn'):
            self.preset_status_btn.set_active(True, preset.name)
            
        if hasattr(self, 'lab_btn'):
            # Set Lab button to ghost (inactive) since Preset is active
            self.lab_btn.set_style_solid(False)
            # Reset icon to default Lab icon to indicate "Preset Mode" / Neutral state
            self.lab_btn.set_main_icon("client/assets/icons/lab_icon.svg")
        
        # 3. Notify CommandPanel that Lab mode is inactive and top bar preset mode is active
        if hasattr(self, 'command_panel'):
            self.command_panel.set_lab_mode_active(False)
            self.command_panel.set_top_bar_preset_mode(True)
            
            self.command_panel.set_top_bar_preset_mode(True)
            
        self._update_footer_mode_active()
        self.update_status(f"Applied Preset: {preset.name}")
        
        # Hide Command Panel with animation (Preset mode is simple drag & drop)
        self.panel_animator.close()

    def on_mode_changed(self, mode):
        """Handle global mode change (e.g. switching to Manual)"""
        # If switching away from Presets (e.g. to Manual or Max Size), reset the preset
        if mode != "Presets":
            self._active_preset = None  # Clear active preset
            if hasattr(self, 'preset_status_btn'):
                self.preset_status_btn.set_active(False)
        
        # Update footer state since preset might be cleared
        self._update_footer_mode_active()
            
        # Notify CommandPanel that top bar preset mode is inactive
        if mode != "Presets" and hasattr(self, 'command_panel'):
            self.command_panel.set_top_bar_preset_mode(False)
