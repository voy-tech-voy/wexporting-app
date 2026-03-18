"""
Main Window for Graphics Conversion App
Implements the layout: Top Bar | Mid Section (Drag-Drop + Commands) | Bottom Bar
"""

import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QDialog, QApplication,
    QGraphicsDropShadowEffect, QSplitter, QStatusBar
)
from PySide6.QtGui import QIcon, QFont, QAction, QColor
from PySide6.QtCore import Qt, Signal, QPoint, QSize, Slot, QTimer, QEvent

from .drag_drop_area import DragDropArea
from .command_panel import CommandPanel
from .output_footer import OutputFooter
from .theme_manager import ThemeManager
from .title_bar import TitleBarWindow
from client.core.tool_manager import ToolChecker  # Only for tool status checking
from client.core.progress_manager import ConversionProgressManager
from client.gui.custom_widgets import PresetStatusButton
from client.utils.font_manager import AppFonts, FONT_FAMILY_APP_NAME
from client.utils.resource_path import get_app_icon_path, get_resource_path
from client.version import APP_NAME, AUTHOR


# Mediator-Shell Architecture Components
from client.gui.animators.side_panel_animator import SidePanelAnimator
from client.gui.components import toast_helpers
from client.gui.components.control_bar import ControlBar
from client.gui.utils.window_behavior import FramelessWindowBehavior
from client.gui.utils.dev_tools import EventDebugFilter, DEBUG_INTERACTIVITY
from client.gui.utils.dialog_manager import DialogManager
from client.gui.drag_drop_area import ViewMode
from client.utils.session_manager import SessionManager

# Conductors (Mediator-Shell Pattern)
from client.core.conductors import (ModeConductor, Mode, ConversionConductor, 
                                     UpdateConductor, VersionGatewayConductor,
                                     ThemeConductor)
from client.gui.dialogs.update_dialog import UpdateDialog
from client.gui.dialogs.version_update_dialogs import (OptionalVersionUpdateDialog, 
                                                        MandatoryVersionUpdateScreen)

# Mixins
from client.gui.mixins import WindowEventMixin


class MainWindow(WindowEventMixin, QMainWindow):
    def __init__(self):
        super().__init__()

        # Install interactive debugger
        if DEBUG_INTERACTIVITY:
            self._debug_filter = EventDebugFilter()
            QApplication.instance().installEventFilter(self._debug_filter)
            print("[DEBUG] Interactive Debug Filter Installed")

        # Development mode detection
        self.DEVELOPMENT_MODE = getattr(sys, '_called_from_test', False) or __debug__ and not getattr(sys, 'frozen', False)

        title = APP_NAME
        if self.DEVELOPMENT_MODE:
            title += " [DEV]"
            
        self.setWindowTitle(title)
        
        # Make window frameless for custom title bar & transparent for rounded corners
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True) # Ensure window accepts drops for the overlay logic
            
        self.setGeometry(*self._compute_initial_geometry())
        self.setMinimumSize(800, 700)
        self.setMouseTracking(True)  # Enable mouse tracking for edge resize cursors
        
        # Set window icon if available
        try:
            from PySide6.QtGui import QIcon
            from client.utils.resource_path import get_app_icon_path
            
            icon_path = get_app_icon_path()
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Could not set window icon: {e}")
        
        # Progress manager for tracking conversion outputs
        self.progress_manager = ConversionProgressManager()
        
        # Theme management (Singleton pattern)
        self.theme_manager = ThemeManager.instance()
        
        # Dialog management (Mediator-Shell: centralized dialogs)
        self.dialogs = DialogManager(self, self.theme_manager)
        
        # Track mouse position for window dragging
        self.drag_position = None
        
        # Mediator-Shell: Window behavior (resize, blur)
        self.window_behavior = FramelessWindowBehavior(self, border_width=8)
        
        # Dev Panel Manager (centralized)
        from client.gui.dev_panels import DevPanelManager, NoiseDevPanel, DevThemePanel, SequenceDevPanel, PurchaseDevPanel
        self.dev_panel_manager = DevPanelManager(self)
        self.dev_panel_manager.register_panel('noise', NoiseDevPanel)
        self.dev_panel_manager.register_panel('theme', DevThemePanel)
        self.dev_panel_manager.register_panel('sequence', SequenceDevPanel)
        self.dev_panel_manager.register_panel('purchase', PurchaseDevPanel)
        
        # Conductors (initialized after UI setup)
        self.mode_conductor = None
        self.conversion_conductor = None
        
        self.setup_ui()
        self.setup_status_bar()
        self.setup_conductors()
        self.connect_signals()
        
        # Connect theme manager signal (now handled by ThemeConductor)
        # ThemeConductor is initialized in setup_conductors() after all widgets exist
        
        self.check_tools()
        
        # Reset drop area rendering after 1ms
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1, self.drag_drop_area.clear_files)

        # Global event filter for clearing statuses
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, source, event):
        """Global event filter to handle click-anywhere behavior"""
        if event.type() == QEvent.Type.MouseButtonPress:
            # Check if conversion is active via conductor - don't clear while working!
            if hasattr(self, 'conversion_conductor') and self.conversion_conductor.is_converting():
                return super().eventFilter(source, event)
                
            # Clear file statuses on any click anywhere in the app (unless persistence is enabled)
            from client.gui.dev_panels.noise_params import NoiseParams
            if hasattr(self, 'drag_drop_area') and not NoiseParams.persistence_enabled:
                self.drag_drop_area.clear_all_statuses()
        
        return super().eventFilter(source, event)
    
    def nativeEvent(self, eventType, message):
        """Pass native events to window behavior handling to enable Windows native snapping/resizing"""
        if hasattr(self, 'window_behavior'):
            handled, result = self.window_behavior.native_event(eventType, message)
            if handled:
                return True, result
        return super().nativeEvent(eventType, message)
        
    def _compute_initial_geometry(self):
        """
        Return (x, y, w, h) that fits within the usable screen area.
        Uses QScreen.availableGeometry() which gives logical pixels
        *after* DPI scaling, excluding the taskbar.
        Safe at 100%, 125%, 150%, 200%, etc.
        """
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        avail  = screen.availableGeometry()   # logical px, excludes taskbar

        IDEAL_W, IDEAL_H = 1200, 1000
        MIN_W,   MIN_H   = 800,  700
        MARGIN = 40  # breathing room on each side

        max_w = avail.width()  - MARGIN * 2
        
        # Max height is 75% of available screen height
        max_h = int(avail.height() * 0.75)

        w = max(MIN_W, min(IDEAL_W, max_w))
        h = max(MIN_H, min(IDEAL_H, max_h))

        x = avail.x() + (avail.width()  - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        return x, y, w, h

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
        
        # Create output footer with progress bars
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
        self.title_bar_window.check_updates_requested.connect(self.check_for_updates_manual)
        self.title_bar_window.buy_credits_requested.connect(self.show_purchase_dialog)
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
    
    def setup_conductors(self):
        """Initialize the Mode and Conversion conductors (Mediator-Shell Pattern)."""
        # Initialize ModeConductor
        self.mode_conductor = ModeConductor(
            control_bar=self.control_bar,
            command_panel=self.command_panel,
            drag_drop_area=self.drag_drop_area,
            panel_animator=self.panel_animator,
            output_footer=self.output_footer,
            lab_btn=self.lab_btn,
            preset_status_btn=self.preset_status_btn,
            right_frame=self.right_frame
        )
        
        # Initialize ConversionConductor
        self.conversion_conductor = ConversionConductor(
            drag_drop_area=self.drag_drop_area,
            command_panel=self.command_panel,
            output_footer=self.output_footer,
            progress_manager=self.progress_manager,
            dialogs=self.dialogs,
            update_status_callback=self.update_status
        )
        
        # Initialize UpdateConductor for content updates
        self.update_conductor = UpdateConductor()
        self.update_conductor.updates_available.connect(self.show_update_dialog)
        self.update_conductor.update_progress.connect(self._on_update_progress)
        self.update_conductor.update_complete.connect(self._on_update_complete)
        self.update_conductor.update_failed.connect(self._on_update_failed)
        self.update_conductor.check_already_running.connect(
            lambda: self.update_status("Update check already in progress...")
        )
        
        # Initialize VersionGatewayConductor for app version updates
        self.version_gateway = VersionGatewayConductor()
        self.version_gateway.optional_update_available.connect(self.show_optional_update)
        self.version_gateway.mandatory_update_required.connect(self.show_mandatory_update)
        
        # Initialize ThemeConductor for theme management
        self.theme_conductor = ThemeConductor(
            theme_manager=self.theme_manager,
            main_window=self,
            drag_drop_area=self.drag_drop_area,
            command_panel=self.command_panel,
            control_bar=self.control_bar,
            output_footer=self.output_footer,
            title_bar_window=self.title_bar_window
        )
        # Apply initial theme
        self.theme_conductor._on_theme_changed(self.theme_manager.is_dark_mode())
        
        self.version_gateway.up_to_date.connect(lambda: self.update_status("App is up to date."))
        self.version_gateway.check_failed.connect(lambda msg: self.update_status(f"Version check failed: {msg}"))

        
        # Version check already ran in main.py before window opened (mandatory update gate).
        # VersionGatewayConductor is kept for manual "Check for updates" only.

        # Content update check (presets/estimators) — different endpoint, run once at startup
        QTimer.singleShot(3000, self.update_conductor.check_for_updates)
        
        # Inject ConversionConductor into PresetOrchestrator (for lab mode preset execution)
        # This must be done after conductor is created
        self.drag_drop_area._setup_preset_plugin(self.conversion_conductor)

        # Clear ConversionConductor preset when switching to Lab mode
        self.mode_conductor.mode_changed.connect(
            lambda mode: self.conversion_conductor.clear_active_preset()
            if mode == Mode.LAB else None
        )

        # Wire start-button hover → credit preview
        self.output_footer.hover_preview_requested.connect(
            lambda: self.output_footer.show_cost_preview(
                self.conversion_conductor.get_preview_cost(
                    self.drag_drop_area.get_files(),
                    self.command_panel.get_conversion_params()
                )
            )
        )
    
    # =========================================================================
    # MODE CONDUCTOR DELEGATION
    # =========================================================================
    # Mode switching logic has been extracted to ModeConductor.
    # MainWindow now delegates to the conductor for all mode-related operations.
    # =========================================================================
    
    @property
    def current_mode(self) -> Mode:
        """Get the current application mode (delegates to ModeConductor)."""
        return self.mode_conductor.current_mode if self.mode_conductor else Mode.PRESET
    
    def _on_preset_btn_clicked(self):
        """Handle preset button click (delegates to ModeConductor)."""
        if self.mode_conductor:
            self.mode_conductor.on_preset_btn_clicked()
    
    def _on_lab_item_clicked(self, item_id):
        """Handle lab button menu item click (delegates to ModeConductor)."""
        if self.mode_conductor:
            self.mode_conductor.on_lab_item_clicked(item_id)
    

    def _on_restore_lab_settings(self, lab_settings: dict):
        """Restore Lab Mode settings from a custom preset."""
        print(f"[MainWindow] Restoring Lab Mode settings: {lab_settings.get('type', 'unknown')}")
        
        # 1. Determine which tab based on type
        file_type = lab_settings.get('type', 'video')
        lab_tab_map = {'image': 0, 'video': 1, 'gif': 2, 'loop': 2}
        lab_tab = lab_tab_map.get(file_type, 1)
        
        # 2. Switch to Lab Mode with the correct tab
        if self.mode_conductor:
            self.mode_conductor.switch_mode(Mode.LAB, lab_tab=lab_tab)
        
        # 3. Hide preset gallery
        self.drag_drop_area.set_view_mode(ViewMode.FILES)
        
        # 4. Restore settings to CommandPanel (with small delay to ensure tab is active)
        QTimer.singleShot(100, lambda: self.command_panel.restore_lab_settings(lab_settings))
    
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
        

        
    def setup_menu_bar(self):
        """Hide the menu bar completely"""
        menubar = self.menuBar()
        menubar.hide()
        
    def setup_status_bar(self):
        """Setup the status bar."""
        # Status bar - hidden (no resize grip shown)
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.setStatusBar(self.status_bar)
        self.status_bar.hide()
        
    def update_status(self, message):
        """Update status in status bar"""
        self.status_bar.showMessage(message)
        

    def connect_signals(self):
        """Connect signals between components"""
        # Connect drag-drop area signals
        self.drag_drop_area.files_added.connect(self.on_files_added)
        self.drag_drop_area.preset_applied.connect(self.on_preset_applied)
        self.drag_drop_area.go_to_lab_requested.connect(self._on_restore_lab_settings)
        # Trigger purchase dialog when insufficient credits toast is dismissed
        self.drag_drop_area.insufficient_credits_dismissed.connect(self.show_purchase_dialog)
        
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
            
        # Show preset gallery only if NOT in LAB mode
        # When LAB mode is active, user is working with the command panel, don't interrupt
        if self.current_mode != Mode.LAB:
            self.drag_drop_area.show_preset_view()
        
        # Invalidate preset gallery blur cache to reflect updated file list
        if hasattr(self.drag_drop_area, '_preset_orchestrator') and self.drag_drop_area._preset_orchestrator:
            if hasattr(self.drag_drop_area._preset_orchestrator, '_gallery') and self.drag_drop_area._preset_orchestrator._gallery:
                gallery = self.drag_drop_area._preset_orchestrator._gallery
                # If gallery is currently visible, force immediate recapture with delay for rendering
                if gallery.isVisible():
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(50, lambda: gallery.capture_blur_background(force=True))
                else:
                    # If not visible, just clear cache so next open captures fresh
                    gallery.clear_blur_cache()
    
    def _on_footer_start(self):
        """Handle start button click from output footer (delegates to ConversionConductor)."""
        # Check if preset mode is active
        if self.conversion_conductor and self.conversion_conductor._active_preset is not None:
            self.conversion_conductor.start_preset_conversion()
            return
        
        # Normal conversion path - get complete payload from command panel
        params = self.command_panel.get_execution_payload()
        
        # Override output settings from footer
        output_mode = self.output_footer.get_output_mode()
        if output_mode == "source":
            params['output_same_folder'] = True
            params['use_nested_output'] = False
            params['output_custom'] = False
        elif output_mode == "organized":
            params['output_same_folder'] = False
            params['use_nested_output'] = True
            params['nested_output_name'] = self.output_footer.get_organized_name()
            params['output_custom'] = False
        elif output_mode == "custom":
            params['output_same_folder'] = False
            params['use_nested_output'] = False
            params['output_custom'] = True
            params['output_dir'] = self.output_footer.get_custom_path()
        
        # Delegate to ConversionConductor
        if self.conversion_conductor:
            self.conversion_conductor.start_conversion(params)
    
    # =========================================================================
    # CONVERSION CONDUCTOR DELEGATION
    # =========================================================================
    # Conversion logic has been extracted to ConversionConductor.
    # MainWindow now delegates to the conductor for all conversion operations.
    # =========================================================================
    
    def start_conversion(self, params):
        """Start conversion (delegates to ConversionConductor)."""
        if self.conversion_conductor:
            self.conversion_conductor.start_conversion(params)
    
    def stop_conversion(self):
        """Stop conversion (delegates to ConversionConductor)."""
        if self.conversion_conductor:
            self.conversion_conductor.stop_conversion()
    
    @property
    def conversion_engine(self):
        """Get conversion engine from conductor (backward compatibility)."""
        return self.conversion_conductor.conversion_engine if self.conversion_conductor else None
    
    @conversion_engine.setter
    def conversion_engine(self, value):
        """Set conversion engine on conductor (backward compatibility)."""
        if self.conversion_conductor:
            self.conversion_conductor.conversion_engine = value
    
    def set_progress(self, value):
        """Set progress bar value (delegates to ConversionConductor)."""
        if self.conversion_conductor:
            self.conversion_conductor.set_progress(value)
    
    @Slot(int, float)
    def on_file_progress(self, file_index, progress):
        """Handle file progress (delegates to ConversionConductor)."""
        if self.conversion_conductor:
            self.conversion_conductor.on_file_progress(file_index, progress)
    
    def on_file_completed(self, source_file, output_file):
        """Handle file completion (delegates to ConversionConductor)."""
        if self.conversion_conductor:
            self.conversion_conductor.on_file_completed(source_file, output_file)
    
    def on_conversion_finished(self, success, message):
        """Handle conversion finished - LEGACY (delegates to ConversionConductor)."""
        if self.conversion_conductor:
            self.conversion_conductor.on_conversion_finished(success, message)
            
    def check_tools(self):
        """Check if required tools are available"""
        tools = ToolChecker.get_tool_status()
        detailed_status = ToolChecker.get_detailed_status()
        
        missing_tools = [tool for tool, available in tools.items() if not available]
        
        if missing_tools:
            # Create detailed message
            message_parts = ["Tool Status Check:\n"]
            for tool, status in detailed_status.items():
                icon = "[OK]" if tools[tool] else "[X]"
                message_parts.append(f"{icon} {tool.title()}: {status}")
            
            message = "\n".join(message_parts)
            message += f"\n\nNote: The app will use fallback methods for missing tools."
            
            self.dialogs.show_tool_status(message)
        
    def toggle_theme(self):
        """Toggle between dark and light theme (delegates to ThemeConductor)"""
        if hasattr(self, 'theme_conductor'):
            self.theme_conductor.toggle_theme()


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
        if preset is None:
            print("[Smart Drop] Clearing preset selection")
            if self.mode_conductor:
                self.mode_conductor.clear_active_preset()
            if self.conversion_conductor:
                self.conversion_conductor.clear_active_preset()
            
            if hasattr(self, 'preset_status_btn'):
                self.preset_status_btn.set_active(False)
            
            self.update_status("Preset cleared")
            return
            
        file_count = len(files) if files else 0
        print(f"[Smart Drop] Applying preset: {preset.name} to {file_count} files")
        
        # Store active preset in conductors
        if self.mode_conductor:
            self.mode_conductor.set_active_preset(preset)
        if self.conversion_conductor:
            self.conversion_conductor.set_active_preset(preset)
        
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
        
        self.update_status(f"Applied Preset: {preset.name}")
        
        # Hide Command Panel with animation (Preset mode is simple drag & drop)
        self.panel_animator.close()

    def on_mode_changed(self, mode):
        """Handle global mode change (e.g. switching to Manual)"""
        # If switching away from Presets (e.g. to Manual or Max Size), reset the preset
        if mode != "Presets":
            # Clear active preset in conductors
            if self.mode_conductor:
                self.mode_conductor.clear_active_preset()
            if self.conversion_conductor:
                self.conversion_conductor.clear_active_preset()
            if hasattr(self, 'preset_status_btn'):
                self.preset_status_btn.set_active(False)
            
        # Notify CommandPanel that top bar preset mode is inactive
        if mode != "Presets" and hasattr(self, 'command_panel'):
            self.command_panel.set_top_bar_preset_mode(False)
    
    def keyPressEvent(self, event):
        """Handle global keyboard shortcuts"""
        from PySide6.QtCore import Qt
        
        # Delegate to DevPanelManager
        if hasattr(self, 'dev_panel_manager') and self.dev_panel_manager.handle_key_event(event):
            return
        
        
        super().keyPressEvent(event)
    
    def check_for_updates_manual(self):
        """Manually trigger update check from title bar (checks both version and content)."""
        self.update_status("Checking for updates...")
        
        # Show toast feedback
        toast_helpers.show_checking_updates_toast(self)
        
        # Check app version first
        if hasattr(self, 'version_gateway'):
            self.version_gateway.check_version()
            
        # Then check content updates
        if hasattr(self, 'update_conductor'):
            # Delay slightly so version check completes first
            QTimer.singleShot(1000, self.update_conductor.check_for_updates)
            
    
    def show_purchase_dialog(self):
        """Show the Purchase Dialog (from Menu)"""
        from client.gui.dialogs.purchase_dialog import PurchaseDialog
        
        # Open Purchase Dialog (handles its own dimming overlay)
        dialog = PurchaseDialog(parent=self)
        return dialog.exec()
        
    def show_update_dialog(self, manifest):
        """Show dialog with available content updates."""
        dialog = UpdateDialog(manifest, self)
        if dialog.exec():
            # User clicked "Update Now" - trigger actual update application
            self.update_status("Downloading updates...")
            self.update_conductor.apply_updates(manifest)
            
    def _on_update_progress(self, message, percentage):
        """Handle update progress updates."""
        self.update_status(f"{message} ({percentage}%)")
        
    def _on_update_complete(self, result):
        """Handle successful update completion."""
        presets_updated = result.get('presets_updated', 0)
        estimators_updated = result.get('estimators_updated', 0)
        errors = result.get('errors', [])
        
        if errors:
            error_msg = "\n".join(errors)
            self.dialogs.show_warning(
                "Updates Partially Applied",
                f"Updated {presets_updated} presets and {estimators_updated} estimators.\n\nErrors:\n{error_msg}"
            )
        else:
            self.dialogs.show_info(
                "Updates Complete",
                f"Successfully updated {presets_updated} presets and {estimators_updated} estimators!"
            )
        
        self.update_status("Updates applied successfully.")
        
    def _on_update_failed(self, error_msg):
        """Handle update failure."""
        self.dialogs.show_error("Update Failed", f"Failed to apply updates:\n{error_msg}")
        self.update_status("Update failed.")
            
    def show_optional_update(self, result):
        """Show dialog for optional app version update."""
        dialog = OptionalVersionUpdateDialog(result, self)
        dialog.exec()
        
    def show_mandatory_update(self, result):
        """Show blocking screen for mandatory app version update."""
        # Create full-screen blocking widget
        self.mandatory_screen = MandatoryVersionUpdateScreen(result)
        self.mandatory_screen.showFullScreen()
            

    def _refresh_file_list_items(self):
        """Force repaint of all file list items to reflect new noise parameters."""
        if hasattr(self, 'drag_drop_area'):
            # Trigger update on all file list item widgets
            for i in range(self.drag_drop_area.file_list_widget.count()):
                item = self.drag_drop_area.file_list_widget.item(i)
                widget = self.drag_drop_area.file_list_widget.itemWidget(item)
                if widget and hasattr(widget, 'update'):
                    widget.update()  # Force repaint
