"""
Command Panel Widget (Refactored)
Container for tab components - delegates all parameter handling to tabs.

This is a CONTAINER, not a controller. It:
1. Holds the tabs (ImageTab, VideoTab, LoopTab)
2. Manages the Global Side Menu (Mode buttons)
3. Routes the final conversion request signal
4. Does NOT contain logic about resize modes or codec settings
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTabWidget, QSizePolicy, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon

from client.gui.tabs import ImageTab, VideoTab, LoopTab
from client.gui.custom_widgets import (
    ModeButtonsWidget, SideButtonGroup, MorphingButton
)
from client.gui.command_group import CommandGroup
from client.utils.resource_path import get_resource_path
from client.utils.theme_utils import is_dark_mode


class CommandPanel(QWidget):
    """
    Container widget for conversion tabs.
    
    Signals:
        conversion_requested: Emitted with conversion parameters dict
        stop_conversion_requested: Emitted to cancel conversion
        global_mode_changed: Emitted when mode (Max Size/Manual/Presets) changes
        lab_state_changed: Emitted for lab button state updates
    """
    
    conversion_requested = Signal(dict)
    stop_conversion_requested = Signal()
    global_mode_changed = Signal(str)
    lab_state_changed = Signal(str, bool)
    
    def __init__(self):
        super().__init__()
        self.is_dark_mode = is_dark_mode()
        self._gpu_detector = None
        self._gpu_available_codecs = set()
        self._top_bar_preset_active = False
        self._lab_mode_active = False
        
        self.setup_ui()
        QTimer.singleShot(100, self._initialize_gpu_detection)
    
    def setup_ui(self):
        """Setup minimal container interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Main Row: Sidebar + Tabs ---
        main_row = QWidget()
        main_layout = QHBoxLayout(main_row)
        main_layout.setContentsMargins(-12, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Sidebar (Mode Buttons + Side Button Stack)
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # 2. Tab Container
        tab_container = self._create_tab_container()
        main_layout.addWidget(tab_container)
        
        layout.addWidget(main_row, 1)
        
        # Initialize state
        self._init_state()
        
        # Connect signals
        self.tabs.currentChanged.connect(self._on_tab_changed)
    
    def _create_sidebar(self) -> QWidget:
        """Create sidebar with mode buttons and side button stack."""
        sidebar = QWidget()
        sidebar.setMinimumWidth(0)
        sidebar.setMaximumWidth(44)
        sidebar.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 100, 0, 0)
        layout.setSpacing(12)
        
        # Mode Buttons (Max Size / Manual / Presets)
        self.mode_buttons = ModeButtonsWidget(
            default_mode="Max Size", 
            orientation=Qt.Orientation.Vertical
        )
        self.mode_buttons.modeChanged.connect(self._on_global_mode_changed)
        layout.addWidget(self.mode_buttons)
        
        layout.addStretch()
        
        # Side Buttons Stack (for transform sections)
        self.side_buttons_stack = QStackedWidget()
        self.side_buttons_stack.setFixedHeight(198)
        layout.addWidget(self.side_buttons_stack)
        
        return sidebar
    
    def _create_tab_container(self) -> QWidget:
        """Create tab widget container."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Tab Widget (hidden tab bar - controlled by Lab Button)
        self.tabs = QTabWidget()
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.tabBar().hide()
        self.tabs.setDocumentMode(True)
        
        # Create tabs using extracted components
        self._image_tab = ImageTab(
            parent=self,
            focus_callback=self._focus_active_tab
        )
        self._video_tab = VideoTab(
            parent=self,
            focus_callback=self._focus_active_tab,
            is_dark_mode=self.is_dark_mode
        )
        self._loop_tab = LoopTab(
            parent=self,
            focus_callback=self._focus_active_tab,
            is_dark_mode=self.is_dark_mode
        )
        
        # Add tabs
        self.tabs.addTab(self._image_tab, QIcon(get_resource_path("client/assets/icons/pic_icon.svg")), "")
        self.tabs.addTab(self._video_tab, QIcon(get_resource_path("client/assets/icons/vid_icon.svg")), "")
        self.tabs.addTab(self._loop_tab, QIcon(get_resource_path("client/assets/icons/loop_icon3.svg")), "")
        
        # Create and add side buttons for each tab
        self._create_side_buttons()
        
        layout.addWidget(self.tabs)
        return container
    
    def _create_side_buttons(self):
        """Create side buttons for transform sections (Resize/Rotate/Time)."""
        # Image tab side buttons (Resize, Rotate only)
        self.image_side_buttons = SideButtonGroup(['resize', 'rotate'])
        self.image_side_buttons.selectionChanged.connect(
            lambda mode: self._image_tab.set_transform_mode(mode)
        )
        self.side_buttons_stack.addWidget(self.image_side_buttons)
        
        # Video tab side buttons (Resize, Rotate, Time)
        self.video_side_buttons = SideButtonGroup(['resize', 'rotate', 'time'])
        self.video_side_buttons.selectionChanged.connect(
            lambda mode: self._video_tab.set_transform_mode(mode)
        )
        self.side_buttons_stack.addWidget(self.video_side_buttons)
        
        # Loop tab side buttons (Resize, Rotate, Time)
        self.loop_side_buttons = SideButtonGroup(['resize', 'rotate', 'time'])
        self.loop_side_buttons.selectionChanged.connect(
            lambda mode: self._loop_tab.set_transform_mode(mode)
        )
        self.side_buttons_stack.addWidget(self.loop_side_buttons)
    
    def _init_state(self):
        """Initialize UI state."""
        # Default to Video tab
        self.tabs.setCurrentIndex(1)
        self.side_buttons_stack.setCurrentIndex(1)
        
        # Track modes per tab
        self.tab_modes = {0: "Max Size", 1: "Max Size", 2: "Max Size"}
        
        # Set initial mode on all tabs
        self._image_tab.set_mode("Max Size")
        self._video_tab.set_mode("Max Size")
        self._loop_tab.set_mode("Max Size")
        
        # Set initial transform visibility (resize)
        self._image_tab.set_transform_mode('resize')
        self._video_tab.set_transform_mode('resize')
        self._loop_tab.set_transform_mode('resize')
    
    # =========================================================================
    # PUBLIC API - Parameters & Signals
    # =========================================================================
    
    def get_conversion_params(self) -> dict:
        """
        Get current conversion parameters by delegating to active tab.
        
        Returns:
            dict: Conversion parameters from the active tab
        """
        current_index = self.tabs.currentIndex()
        
        # Base params (output settings - to be merged by MainWindow)
        params = {
            'output_dir': '',
            'use_nested_output': False,
            'nested_output_name': 'output',
            'suffix': '_converted',
            'overwrite': True,
        }
        
        # Delegate to active tab
        if current_index == 0:
            params.update(self._image_tab.get_params())
        elif current_index == 1:
            params.update(self._video_tab.get_params())
        elif current_index == 2:
            params.update(self._loop_tab.get_params())
        
        return params
    
    def get_parameters(self) -> dict:
        """Alias for get_conversion_params (Mediator-Shell API)."""
        return self.get_conversion_params()
    
    def get_execution_payload(self) -> dict:
        """Get complete execution payload for ConversionEngine."""
        params = self.get_conversion_params()
        # Add any additional payload data needed
        return params
    
    def start_conversion(self):
        """Emit conversion request signal."""
        self.conversion_requested.emit(self.get_conversion_params())
    
    # =========================================================================
    # MODE & TAB MANAGEMENT
    # =========================================================================
    
    def _on_global_mode_changed(self, mode: str):
        """Handle mode change from global mode buttons."""
        current_index = self.tabs.currentIndex()
        self.tab_modes[current_index] = mode
        
        # Delegate mode change to active tab
        if current_index == 0:
            self._image_tab.set_mode(mode)
        elif current_index == 1:
            self._video_tab.set_mode(mode)
        elif current_index == 2:
            self._loop_tab.set_mode(mode)
        
        # Update side buttons visibility
        self._update_side_buttons_visibility(mode)
        
        # Emit signal
        self.global_mode_changed.emit(mode)
    
    def _on_tab_changed(self, index: int):
        """Handle tab change - sync mode buttons and side buttons."""
        # Sync side buttons stack
        self.side_buttons_stack.setCurrentIndex(index)
        
        # Sync mode buttons to this tab's mode
        saved_mode = self.tab_modes.get(index, "Max Size")
        self.mode_buttons.set_mode(saved_mode)
        
        # Update UI icons
        self.update_tab_icons()
    
    def _update_side_buttons_visibility(self, mode: str):
        """Update side buttons visibility based on mode."""
        # Side buttons visible in Manual mode only (or when Lab mode active)
        visible = (mode == "Manual") or self._lab_mode_active
        
        # Get current side buttons
        current_buttons = self.side_buttons_stack.currentWidget()
        if current_buttons:
            current_buttons.setVisible(visible)
    
    def update_tab_icons(self, activate_lab: bool = False):
        """Update Lab Button icon based on active tab."""
        current_index = self.tabs.currentIndex()
        icons = [
            "client/assets/icons/pic_icon.svg",
            "client/assets/icons/vid_icon.svg", 
            "client/assets/icons/loop_icon3.svg"
        ]
        icon_path = get_resource_path(icons[current_index])
        self.lab_state_changed.emit(icon_path, activate_lab)
    
    def set_current_tab(self, index: int):
        """Set current tab by index."""
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)
    
    def _on_tab_btn_clicked(self, btn_id: int):
        """Handle MorphingButton menu item click (for MainWindow Lab Button)."""
        self.set_current_tab(btn_id)
        self.update_tab_icons(activate_lab=True)
    
    def set_lab_mode_active(self, active: bool):
        """Set whether Lab mode is active."""
        self._lab_mode_active = active
        mode = self.mode_buttons.get_mode() if hasattr(self, 'mode_buttons') else "Max Size"
        self._update_side_buttons_visibility(mode)
    
    def set_top_bar_preset_mode(self, active: bool):
        """Set whether top bar preset mode is active."""
        self._top_bar_preset_active = active
    
    # =========================================================================
    # THEME & GPU
    # =========================================================================
    
    def update_theme(self, is_dark: bool):
        """Update theme on all tabs."""
        self.is_dark_mode = is_dark
        self._image_tab.update_theme(is_dark)
        self._video_tab.update_theme(is_dark)
        self._loop_tab.update_theme(is_dark)
    
    def _initialize_gpu_detection(self):
        """Initialize GPU detection for codec acceleration."""
        try:
            from client.utils.gpu_detector import get_gpu_detector
            from client.core.conversion_engine_validation import validate_system_ffmpeg
            
            is_valid, error_msg, ffmpeg_path, version_info = validate_system_ffmpeg()
            if not is_valid or not ffmpeg_path:
                ffmpeg_path = "ffmpeg"
            
            self._gpu_detector = get_gpu_detector(ffmpeg_path)
            encoders = self._gpu_detector.detect_encoders()
            
            # Determine GPU-accelerated codecs
            if any(e in encoders for e in ['h264_nvenc', 'h264_amf', 'h264_qsv']):
                self._gpu_available_codecs.add('h264')
            if any(e in encoders for e in ['hevc_nvenc', 'hevc_amf', 'hevc_qsv']):
                self._gpu_available_codecs.add('hevc')
            if any(e in encoders for e in ['av1_nvenc', 'av1_amf', 'av1_qsv']):
                self._gpu_available_codecs.add('av1')
            if 'vp9_qsv' in encoders:
                self._gpu_available_codecs.add('vp9')
            
            print(f"GPU Detector: Available GPU codecs: {self._gpu_available_codecs}")
            
            # Update video tab with GPU info
            if hasattr(self._video_tab, 'codec') and hasattr(self._video_tab.codec, 'update_gpu_status'):
                self._video_tab.codec.update_gpu_status(self._gpu_available_codecs)
                
        except Exception as e:
            print(f"GPU Detection failed: {e}")
            self._gpu_available_codecs = set()
    
    # =========================================================================
    # UTILITY
    # =========================================================================
    
    def _focus_active_tab(self):
        """Set focus to the currently active tab."""
        current_widget = self.tabs.currentWidget()
        if current_widget:
            current_widget.setFocus()
    
    # =========================================================================
    # BACKWARDS COMPATIBILITY PROPERTIES
    # =========================================================================
    
    @property
    def image_tab(self):
        """Access image tab (for MainWindow compatibility)."""
        return self._image_tab
    
    @property
    def video_tab(self):
        """Access video tab (for MainWindow compatibility)."""
        return self._video_tab
    
    @property
    def loop_tab(self):
        """Access loop tab (for MainWindow compatibility)."""
        return self._loop_tab
