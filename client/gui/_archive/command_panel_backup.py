"""
Command Panel Widget
Provides conversion commands and options for ffmpeg, gifsicle, and ImageMagick
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit,
    QGroupBox, QFormLayout, QTabWidget, QTextEdit, QSlider, QRadioButton, QSizePolicy, QButtonGroup,
    QProgressBar, QFrame, QStackedWidget
)
from client.core.presets import (
    VIDEO_QUALITY_PRESETS_STANDARD,
    VIDEO_QUALITY_PRESETS_AUTORESIZE,
    BG_STYLE_BLACK_BARS,
    BG_STYLE_BLURRED,
    BG_STYLE_FILL_ZOOM,
    LOOP_PRESETS
)
from client.utils.font_manager import AppFonts, FONT_FAMILY, FONT_FAMILY_APP_NAME, FONT_SIZE_BUTTON
from client.gui.custom_widgets import (
    TimeRangeSlider, ResizeFolder, RotationOptions, CustomComboBox,
    CustomTargetSizeSpinBox, ModeButtonsWidget, PresetButton,
    SquareButtonRow, SideButtonGroup, AnimatedSideModeButton, FormatButtonRow, RotationButtonRow,
    LoopFormatSelector, GPUIndicator, VideoCodecSelector, install_app_tooltip, MorphingButton, PresetStatusButton,
    ThemedCheckBox, DynamicFontButton
)
from client.gui.custom_spinbox import CustomSpinBox
from client.gui.command_group import CommandGroup
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QTimer, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QIcon, QPixmap
from client.utils.resource_path import get_resource_path
from client.utils.theme_utils import is_dark_mode
import json
import winreg


# Determine background color based on theme
BG_COLOR = "#2b2b2b" if is_dark_mode() else "#ffffff"
TEXT_COLOR = "white" if is_dark_mode() else "black"

from client.gui.theme_variables import get_color

def get_toggle_style(is_dark):
    """Get Tesla-style toggle switch stylesheet based on theme"""
    border_dim = get_color("border_dim", is_dark)
    accent_success = get_color("accent_success", is_dark)
    text_color = get_color("text_primary", is_dark)
    
    return f"""
        QCheckBox, QRadioButton {{ 
            color: {text_color}; 
            spacing: 8px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{ 
            width: 32px; 
            height: 18px; 
            border-radius: 9px;
        }}
        QCheckBox::indicator:unchecked, QRadioButton::indicator:unchecked {{ 
            background-color: {border_dim}; 
            border: 1px solid {border_dim};
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ 
            background-color: {accent_success}; 
            border: 1px solid {accent_success};
        }}
        /* Hover styles */
        QCheckBox::indicator:unchecked:hover, QRadioButton::indicator:unchecked:hover {{ 
            border: 1px solid #555;
        }}
    """

# Initial style
TOGGLE_STYLE = get_toggle_style(is_dark_mode())

def get_combobox_style(is_dark):
    """Get QComboBox style that respects dark/light mode with chevron arrow"""
    bg_color = "#2b2b2b" if is_dark else "#ffffff"
    text_color = "white" if is_dark else "black"
    border_color = "#555555" if is_dark else "#cccccc"
    dropdown_bg = bg_color  # Match main background
    arrow_color = "#AAAAAA" if is_dark else "#888888"
    
    return (
        f"QComboBox {{ "
        f"background-color: {bg_color}; "
        f"color: {text_color}; "
        f"border: 1px solid {border_color}; "
        f"border-radius: 4px; "
        f"padding: 4px 25px 4px 8px; "
        f"}} "
        f"QComboBox:hover {{ border-color: #4CAF50; }} "
        f"QComboBox::drop-down {{ "
        f"subcontrol-origin: padding; "
        f"subcontrol-position: top right; "
        f"width: 20px; "
        f"border: none; "
        f"background-color: {dropdown_bg}; "
        f"}} "
        f"QComboBox::down-arrow {{ "
        f"image: none; "
        f"width: 0; "
        f"height: 0; "
        f"border-left: 5px solid transparent; "
        f"border-right: 5px solid transparent; "
        f"border-top: 6px solid {arrow_color}; "
        f"margin-right: 5px; "
        f"}} "
        f"QComboBox QAbstractItemView {{ "
        f"background-color: {bg_color}; "
        f"color: {text_color}; "
        f"selection-background-color: #4CAF50; "
        f"selection-color: white; "
        f"border: 1px solid {border_color}; "
        f"}}"
    )

COMBOBOX_STYLE = get_combobox_style(is_dark_mode())


# Keep QRangeSlider as an alias for backwards compatibility
QRangeSlider = TimeRangeSlider

# =============================================================================
# FEATURE FLAGS FOR SAFE TAB INTEGRATION (Phase 3+ Refactoring)
# Set to True to use new extracted tab components, False for legacy code
# =============================================================================
USE_NEW_IMAGE_TAB = True  # Phase A: ImageTab integration - TESTING
USE_NEW_VIDEO_TAB = True  # Phase B: VideoTab integration - TESTING  
USE_NEW_LOOP_TAB = True   # Phase C: LoopTab integration - TESTING


class CommandPanel(QWidget):
    conversion_requested = Signal(dict)  # Signal with conversion parameters
    stop_conversion_requested = Signal()  # Signal to stop conversion
    global_mode_changed = Signal(str) # Signal when global mode changes
    lab_state_changed = Signal(str, bool) # Signal: (icon_path, is_solid) for lab button updates
    
    def __init__(self):
        super().__init__()
        self.is_dark_mode = is_dark_mode()
        self._gpu_detector = None  # Lazy-loaded GPU detector
        self._gpu_available_codecs = set()  # Codecs with GPU acceleration
        self._top_bar_preset_active = False  # Track if top bar preset mode is ON
        self._lab_mode_active = False  # Track if Lab mode is ON (Lab button active)
        self.setup_ui()
        # NOTE: Convert button initialization moved to OutputFooter
        # Initialize GPU detection after UI is ready
        QTimer.singleShot(100, self._initialize_gpu_detection)
    


    def _initialize_gpu_detection(self):
        """Initialize GPU detection and determine which codecs have acceleration"""
        try:
            from client.utils.gpu_detector import get_gpu_detector
            from client.core.conversion_engine_validation import validate_system_ffmpeg
            
            # Get validated ffmpeg path
            is_valid, error_msg, ffmpeg_path, version_info = validate_system_ffmpeg()
            if not is_valid or not ffmpeg_path:
                ffmpeg_path = "ffmpeg"  # Fallback to system PATH
                
            self._gpu_detector = get_gpu_detector(ffmpeg_path)
            encoders = self._gpu_detector.detect_encoders()
            
            # Determine which codecs have GPU acceleration
            self._gpu_available_codecs = set()
            
            # Check for H.264 GPU
            if any(e in encoders for e in ['h264_nvenc', 'h264_amf', 'h264_qsv']):
                self._gpu_available_codecs.add('h264')
                
            # Check for HEVC/H.265 GPU
            if any(e in encoders for e in ['hevc_nvenc', 'hevc_amf', 'hevc_qsv']):
                self._gpu_available_codecs.add('hevc')
                
            # Check for AV1 GPU (RTX 40 series only for NVIDIA)
            if any(e in encoders for e in ['av1_nvenc', 'av1_amf', 'av1_qsv']):
                self._gpu_available_codecs.add('av1')
                
            # Check for VP9 GPU (only Intel QSV has VP9 HW encoding)
            if 'vp9_qsv' in encoders:
                self._gpu_available_codecs.add('vp9')
                
            print(f"GPU Detector: Available GPU codecs: {self._gpu_available_codecs}")
            print(f"GPU Detector: Found encoders: {encoders}")
            
            # Update indicator based on current tab/format
            self._update_gpu_indicator()
            
            # Update video codec buttons with GPU status
            if hasattr(self, 'video_codec') and hasattr(self.video_codec, 'update_gpu_status'):
                self.video_codec.update_gpu_status(self._gpu_available_codecs)
            
        except Exception as e:
            print(f"GPU Detection failed: {e}")
            self._gpu_available_codecs = set()
            # Still try to update button state to false
            if hasattr(self, 'convert_btn'):
                self.convert_btn.set_gpu_available(False)
                
    def _update_gpu_indicator(self):
        """Update GPU state for UI elements based on currently selected format"""
        # Determine format based on current tab
        current_tab = self.tabs.currentIndex() if hasattr(self, 'tabs') else 0
        gpu_available = False
        
        if current_tab == 0:  # Image tab - no GPU for images
            gpu_available = False
            
        elif current_tab == 1:  # Video tab
            if hasattr(self, 'video_codec'):
                codec_text = self.video_codec.currentText()
                if 'H.264' in codec_text:
                    gpu_available = 'h264' in self._gpu_available_codecs
                elif 'H.265' in codec_text or 'HEVC' in codec_text:
                    gpu_available = 'hevc' in self._gpu_available_codecs
                elif 'AV1' in codec_text:
                    gpu_available = 'av1' in self._gpu_available_codecs
                    
        elif current_tab == 2:  # Loop tab
            if hasattr(self, 'loop_format'):
                format_text = self.loop_format.currentText()
                if 'GIF' in format_text:
                    gpu_available = False  # GIF doesn't use GPU
                elif 'VP9' in format_text:
                    gpu_available = 'vp9' in self._gpu_available_codecs
                elif 'AV1' in format_text:
                    gpu_available = 'av1' in self._gpu_available_codecs
                    
        # Update the convert button GPU state for visual effects
        if hasattr(self, 'convert_btn'):
            self.convert_btn.set_gpu_available(gpu_available)

    def _create_label_with_icon(self, text, icon_path):
        """Create a QLabel with an icon and text"""
        from PySide6.QtGui import QPixmap, QPainter, QIcon
        from PySide6.QtCore import QColor
        from client.utils.resource_path import get_resource_path
        import os
        
        container = QWidget()
        container.setMinimumHeight(28)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Icon label
        icon_label = QLabel()
        icon_label.setFixedSize(16, 16)
        
        if icon_path:
            # Resolve absolute path for the bundle
            abs_icon_path = get_resource_path(icon_path)
            # Load SVG icon from assets (SVG preferred for crisp rendering)
            svg_path = abs_icon_path.replace('.png', '.svg')
            
            if os.path.exists(svg_path):
                # Use QIcon for high-quality SVG rendering
                icon = QIcon(svg_path)
                pixmap = icon.pixmap(16, 16)
                icon_label.setPixmap(pixmap)
            elif os.path.exists(abs_icon_path):
                pixmap = QPixmap(abs_icon_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    icon_label.setPixmap(scaled_pixmap)
                else:
                    icon_label.setStyleSheet("background-color: red;")
            else:
                icon_label.setStyleSheet("background-color: red;")
        else:
            icon_label.setStyleSheet("background-color: red;")
        
        # Create text label
        text_label = QLabel(text)
        text_label.setWordWrap(False)
        
        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch()
        
        return container

    def _create_group_box(self, title, icon_path, size_policy=None):
        """Create a standardized group box with icon and title.
        
        This ensures consistent styling across all tabs:
        - Same padding and margins
        - Same icon size and placement
        - Same title styling
        
        Args:
            title: The group box title text
            icon_path: Path to the icon file
            size_policy: Optional QSizePolicy.Policy for vertical sizing
            
        Returns:
            tuple: (group_box, content_layout) - the group box and its form layout for content
        """
        group = QGroupBox()
        group.setTitle("")  # Will add icon+text manually
        
        if size_policy:
            group.setSizePolicy(group.sizePolicy().horizontalPolicy(), size_policy)
        else:
            group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Outer layout for the group
        outer_layout = QVBoxLayout(group)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        # Title widget with icon
        title_widget = self._create_label_with_icon(title, icon_path)
        # Adjusted padding: 12px top/bottom matches 12px left/right
        title_widget.setStyleSheet("font-weight: bold; padding: 12px 12px; background-color: transparent;")
        outer_layout.addWidget(title_widget)
        
        # Content form layout with consistent margins
        content_layout = QFormLayout()
        content_layout.setContentsMargins(12, 8, 12, 12)
        # Increased spacing between parameters (was 8)
        content_layout.setVerticalSpacing(14)
        outer_layout.addLayout(content_layout)
        
        return group, content_layout
        
    def _get_tinted_icon(self, icon_path, color):
        """Create a tinted QIcon from an SVG path"""
        abs_path = get_resource_path(icon_path)
        
        # Use QIcon to render SVG at target size (32x32) for sharpness
        source_icon = QIcon(abs_path)
        pixmap = source_icon.pixmap(32, 32)
        
        if pixmap.isNull():
            return QIcon()
            
        tinted_pixmap = QPixmap(pixmap.size())
        tinted_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(tinted_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted_pixmap.rect(), color)
        painter.end()
        
        return QIcon(tinted_pixmap)

    def update_tab_icons(self, activate_lab=False):
        """Update Lab Button icon based on active tab
        
        Args:
            activate_lab: If True, sets lab button to active/solid state. 
                         If False (default), only updates the icon without changing state.
        """
        # Ensure buttons exist
        if not hasattr(self, 'lab_btn'):
            return
            
        current_index = self.tabs.currentIndex()
        
        # Icon paths matching tab order
        icons = [
            "client/assets/icons/pic_icon2.svg",
            "client/assets/icons/vid_icon2.svg",
            "client/assets/icons/loop_icon3.svg"
        ]
        
        if 0 <= current_index < len(icons) and activate_lab:
            # Emit signal to update Lab Button (now in MainWindow)
            self.lab_state_changed.emit(icons[current_index], True)


    def _on_tab_btn_clicked(self, btn_id):
        """Handle MorphingButton menu item click (btn_id is item ID)"""
        print(f"[DEBUG_COMMAND] Received Lab Button Click Signal. ID={btn_id}")
        
        # Convert item ID to index if needed (they map 1:1 currently)
        index = btn_id
        if self.tabs.currentIndex() != index:
            print(f"    RESULT: Switching TO -> {btn_id} (Success)")
            self.tabs.setCurrentIndex(index)
        else:
            print(f"    RESULT: Tab {index} already active, refreshing icons")
        
        # Always activate lab button when user explicitly clicks lab menu item
        # This ensures clicking Lab button always exits preset mode and activates lab
        self.update_tab_icons(activate_lab=True)



    def update_theme(self, is_dark):
        """Update theme-dependent styles"""
        self.is_dark_mode = is_dark
        combobox_style = get_combobox_style(is_dark)
        
        # Update all ThemedCheckBox controls automatically
        from client.gui.custom_widgets import ThemedCheckBox
        themed_checkboxes = self.findChildren(ThemedCheckBox)
        for checkbox in themed_checkboxes:
            checkbox.update_theme(is_dark)
        
        # Update all ComboBox controls
        comboboxes = self.findChildren(QComboBox)
        for combobox in comboboxes:
            if isinstance(combobox, CustomComboBox):
                combobox.update_theme(is_dark)
            else:
                combobox.setStyleSheet(combobox_style)
        
        # Update custom widgets
        if hasattr(self, 'time_range_slider'):
            self.time_range_slider.update_theme_colors(is_dark)
        
        resize_folders = self.findChildren(ResizeFolder)
        for rf in resize_folders:
            rf.update_theme(is_dark, combobox_style)
        
        rotation_options = self.findChildren(RotationOptions)
        for ro in rotation_options:
            ro.update_theme(is_dark, combobox_style)
        
        # Update CustomTargetSizeSpinBox widgets
        from client.gui.custom_widgets import CustomTargetSizeSpinBox
        target_size_spinboxes = self.findChildren(CustomTargetSizeSpinBox)
        for spinbox in target_size_spinboxes:
            spinbox.update_theme(is_dark)
        
        # Update CustomSpinBox widgets
        from client.gui.custom_spinbox import CustomSpinBox
        custom_spinboxes = self.findChildren(CustomSpinBox)
        for spinbox in custom_spinboxes:
            spinbox.update_theme(is_dark)
        
        # Update preset buttons
        preset_buttons = self.findChildren(PresetButton)
        for btn in preset_buttons:
            btn.update_theme(is_dark)

        # Update global side buttons
        if hasattr(self, 'mode_buttons'):
            self.mode_buttons.update_theme(is_dark)
        if hasattr(self, 'transform_buttons'):
            self.transform_buttons.update_theme(is_dark)
        
        # NOTE: output_side_btn and output_group have been moved to OutputFooter

        # Tab icons remain at original size (no tinting)

        # Update tab buttons styling
        # Replicating original green tab look
        tab_btn_style = """
            QPushButton {
                background-color: transparent;
                border: 1px solid rgba(128, 128, 128, 0.3);
                border-radius: 6px;
                margin: 2px;
            }
            QPushButton:checked {
                background-color: #00AA00;
                border: 1px solid #008800;
            }
            QPushButton:hover:!checked {
                background-color: rgba(0, 170, 0, 0.2);
            }
        """
        
        if hasattr(self, 'btn_tab_image'):
            self.btn_tab_image.setStyleSheet(tab_btn_style)
            self.btn_tab_video.setStyleSheet(tab_btn_style)
            self.btn_tab_loop.setStyleSheet(tab_btn_style)
        
        # Note: lab_btn has been moved to MainWindow's control bar
        
        # Update all MorphingButton instances
        morphing_buttons = self.findChildren(MorphingButton)
        for mb in morphing_buttons:
            mb.update_theme(is_dark)

        # Update all ModeButtonsWidget and SideButtonGroup instances
        mode_buttons = self.findChildren(ModeButtonsWidget)
        for mb in mode_buttons:
            mb.update_theme(is_dark)
        
        side_buttons = self.findChildren(SideButtonGroup)
        for sb in side_buttons:
            sb.update_theme(is_dark)
        
        # Update rotation button rows
        rotation_rows = self.findChildren(RotationButtonRow)
        for row in rotation_rows:
            row.update_theme(is_dark)
        
        # Update loop format selector
        loop_selectors = self.findChildren(LoopFormatSelector)
        for selector in loop_selectors:
            selector.update_theme(is_dark)

        # Update video codec selector
        video_selectors = self.findChildren(VideoCodecSelector)
        for selector in video_selectors:
            selector.update_theme(is_dark)
        
        # NOTE: nested_output_name and output_dir styling removed - widgets moved to OutputFooter
        
        # Update tab icons (tinting)
        self.update_tab_icons()
        
        # Update global tooltip singleton theme
        from client.gui.custom_widgets import AppTooltip
        if AppTooltip._instance is not None:
            AppTooltip._instance.update_theme(is_dark)
    
    # NOTE: _update_nested_output_style and _update_custom_output_style removed - moved to OutputFooter

    def setup_ui(self):
        """Setup the command panel interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Row 1: Functionality (Sidebar Top + Tabs) ---
        row1_widget = QWidget()
        row1_layout = QHBoxLayout(row1_widget)
        row1_layout.setContentsMargins(-12, 0, 0, 0) # Negative margin for sidebar protrusion
        row1_layout.setSpacing(0)
        
        # 1. Sidebar Top (Mode Buttons + Stack)
        sidebar_top = QWidget()
        # Allow shrinking for animation: Min 0, Max 44
        sidebar_top.setMinimumWidth(0)
        sidebar_top.setMaximumWidth(44)
        sb_top_layout = QVBoxLayout(sidebar_top)
        sb_top_layout.setContentsMargins(0, 100, 0, 0) # 100px top margin
        sb_top_layout.setSpacing(12)
        
        # Mode Buttons
        self.mode_buttons = ModeButtonsWidget(default_mode="Max Size", orientation=Qt.Orientation.Vertical)
        self.mode_buttons.modeChanged.connect(self._on_global_mode_changed)
        sb_top_layout.addWidget(self.mode_buttons)
        
        # Spacer to push stack to bottom (aligned with Transform folder)
        sb_top_layout.addStretch()
        
        # Side Buttons Stack
        self.side_buttons_stack = QStackedWidget()
        self.side_buttons_stack.setFixedHeight(198) # Match height of Transform folder
        sb_top_layout.addWidget(self.side_buttons_stack)
        
        # Allow sidebar to be transparent/pass-through
        sidebar_top.setStyleSheet("background: transparent;")
        sidebar_top.raise_()
        
        row1_layout.addWidget(sidebar_top)
        
        # 2. Right Content Area (Tab Pages only - Lab Button moved to MainWindow)
        right_content_widget = QWidget()
        right_content_layout = QVBoxLayout(right_content_widget)
        right_content_layout.setContentsMargins(0, 0, 0, 0)
        right_content_layout.setSpacing(0)
        
        # Note: Top bar with Lab Button has been moved to MainWindow's control bar
        
        # Pages Container (QTabWidget)
        self.tabs = QTabWidget()
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.tabBar().hide() # Hide native tab bar
        self.tabs.setDocumentMode(True)
        right_content_layout.addWidget(self.tabs)
        
        row1_layout.addWidget(right_content_widget)
        
        layout.addWidget(row1_widget, 1)  # Stretch factor 1: expand to fill vertical space
        
        # DEBUG: Visual marker for tabs widget bottom edge (Between Rows)
        tabs_end_marker = QWidget()
        tabs_end_marker.setFixedHeight(0)
        tabs_end_marker.setStyleSheet("background-color: rgba(255, 0, 0, 255);")
        tabs_end_label = QLabel("TABS-END", tabs_end_marker)
        tabs_end_label.setStyleSheet("color: white; font-size: 9px; font-weight: bold;")
        tabs_end_label.move(2, -6)
        layout.addWidget(tabs_end_marker)
        
        # NOTE: Output settings (Row 2) has been moved to OutputFooter in main_window.py
        
        # --- Content Initialization ---
        
        # Image conversion tab
        self.image_tab = self.create_image_tab()
        self.tabs.addTab(self.image_tab, QIcon(get_resource_path("client/assets/icons/pic_icon.svg")), "")
        # Add side buttons to global stack
        if hasattr(self, 'image_side_buttons'):
            self.side_buttons_stack.addWidget(self.image_side_buttons)
        
        # Video conversion tab
        self.video_tab = self.create_video_tab()
        self.tabs.addTab(self.video_tab, QIcon(get_resource_path("client/assets/icons/vid_icon.svg")), "")
        if hasattr(self, 'video_side_buttons'):
            self.side_buttons_stack.addWidget(self.video_side_buttons)
        
        # Loop conversion tab (was GIF)
        self.loop_tab = self.create_loop_tab()
        self.tabs.addTab(self.loop_tab, QIcon(get_resource_path("client/assets/icons/loop_icon3.svg")), "")
        if hasattr(self, 'loop_side_buttons'):
            self.side_buttons_stack.addWidget(self.loop_side_buttons)
        
        # Select Video tab by default
        self.tabs.setCurrentIndex(1)
        self.side_buttons_stack.setCurrentIndex(1)
        
        # Initialize UI state
        self.on_image_size_mode_changed("Max Size")
        self.on_video_size_mode_changed("Max Size")
        self.on_loop_size_mode_changed("Max Size")
        self.mode_buttons.set_mode("Max Size")
        
        self.tab_modes = {
            0: "Max Size",
            1: "Max Size",
            2: "Max Size"
        }
        
        # Initialize transform visibility
        self._update_image_transform_visibility('resize')
        self._update_video_transform_visibility('resize')
        self._update_loop_transform_visibility('resize')
        
        
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        # Initialize buttons to OFF state
        # Note: lab_btn and preset_status_btn are now in MainWindow's control bar
        # Initial state is set by MainWindow
        
        

        
        # DEBUG: Gap between output folder and convert button
        layout.addWidget(self._create_debug_spacer(9))
        
        # Control buttons (Row 3 - Aligned with content)
        # NOTE: Control buttons (START/STOP) have been moved to OutputFooter in main_window.py
        
        # Install event filter
        self._install_input_field_filters()
        
        # Force initial UI visibility update
        # This ensures side buttons are hidden if Lab Mode is OFF (default)
        initial_mode = "Max Size"
        # If we have mode buttons, check what they say
        if hasattr(self, 'mode_buttons'):
            try:
                initial_mode = self.mode_buttons.get_mode()
            except: pass
             
        self._on_global_mode_changed(initial_mode)
        
    def _install_input_field_filters(self):
        """Install event filter on all input fields to handle Enter key"""
        from client.gui.custom_widgets import CustomTargetSizeSpinBox
        
        # Get all CustomTargetSizeSpinBox lineEdits to exclude them (they handle Enter themselves)
        custom_spinbox_lineedits = set()
        custom_spinboxes = self.findChildren(CustomTargetSizeSpinBox)
        for custom_spinbox in custom_spinboxes:
            custom_spinbox_lineedits.add(custom_spinbox.spinbox.lineEdit())
        
        # Find all QLineEdit widgets (excluding those in CustomTargetSizeSpinBox)
        line_edits = self.findChildren(QLineEdit)
        for line_edit in line_edits:
            if line_edit not in custom_spinbox_lineedits:
                line_edit.installEventFilter(self)
        
        # Find all QSpinBox widgets (including their internal lineEdits)
        spin_boxes = self.findChildren(QSpinBox)
        for spin_box in spin_boxes:
            spin_box.lineEdit().installEventFilter(self)
        
        # Find all QDoubleSpinBox widgets - but exclude those inside CustomTargetSizeSpinBox
        double_spin_boxes = self.findChildren(QDoubleSpinBox)
        for double_spin_box in double_spin_boxes:
            if double_spin_box.lineEdit() not in custom_spinbox_lineedits:
                double_spin_box.lineEdit().installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Filter Enter key presses in input fields to switch focus to active tab button"""
        from PySide6.QtCore import QEvent, Qt
        
        # Check if this is a KeyPress event
        if event.type() == QEvent.Type.KeyPress:
            # Explicitly allow arrow keys to propagate (for spinbox navigation)
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
                return False  # Let arrow keys pass through
            
            # Handle Enter/Return keys only
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Check if the object is an input field
                if isinstance(obj, QLineEdit):
                    # Clear focus from the input field first
                    obj.clearFocus()
                    
                    # Set focus to the tab button
                    self._focus_active_tab()
                    
                    return True  # Event handled
        
        # Let all other events propagate normally
        return False  # Changed from super().eventFilter() to explicit False
    
    def _focus_active_tab(self):
        """Set focus to the currently active tab button"""
        from PySide6.QtWidgets import QApplication
        # Clear current focus first
        focus_widget = QApplication.focusWidget()
        if focus_widget:
            focus_widget.clearFocus()
        tab_bar = self.tabs.tabBar()
        tab_bar.setFocus()

    def _create_transform_side_buttons(self, tab_type):
        """Create side buttons for transform group (Resize, Rotate, Time)"""
        btns_config = [
            {'id': 'resize', 'icon_path': 'client/assets/icons/scale.png', 'tooltip': 'Resize Options'},
            {'id': 'rotate', 'icon_path': 'client/assets/icons/rotate.svg', 'tooltip': 'Rotation Options'}
        ]
        
        # Add Time button only for Video and GIF
        if tab_type in ['video', 'gif']:
            btns_config.append({'id': 'time', 'icon_path': 'client/assets/icons/time.png', 'tooltip': 'Time Options'})
            
        group = SideButtonGroup(btns_config, default_selection='resize')
        # Align buttons 15px below the top edge of the stack (which matches Transform folder top)
        if group.layout():
            group.layout().setContentsMargins(0, 15, 0, 0)
        return group

    def _on_lab_style_changed(self, is_active):
        """Handle Lab Button style change (Active/Solid vs Inactive/Ghost)"""
        # Refresh UI visibility based on new lab state
        current_tab = self.tabs.currentIndex()
        mode = self.tab_modes.get(current_tab, "Max Size")
        
        # Update content visibility
        if current_tab == 0: self.on_image_size_mode_changed(mode)
        elif current_tab == 1: self.on_video_size_mode_changed(mode)
        elif current_tab == 2: self.on_loop_size_mode_changed(mode)
            
        # Update side buttons visibility
        self._on_global_mode_changed(mode)

    def _on_global_mode_changed(self, mode):
        """Handle mode change from the global vertical buttons"""
        self.global_mode_changed.emit(mode)
        
        current_tab = self.tabs.currentIndex()
        self.tab_modes[current_tab] = mode
        
        # Dispatch to specific logic
        if current_tab == 0:
            self.on_image_size_mode_changed(mode)
        elif current_tab == 1:
            self.on_video_size_mode_changed(mode)
        elif current_tab == 2:
            self.on_loop_size_mode_changed(mode)
            
        # Side Buttons visibility:
        # User Rule: Show ONLY when Lab Mode is ON (Lab button active) AND Top Bar Preset Mode is OFF
        should_hide_side = (not self._lab_mode_active) or self._top_bar_preset_active
        
        # User Rule: Colored ONLY in Lab Mode (Manual). Uncolored in Max Size.
        should_be_colored = (mode == "Manual")
        
        if hasattr(self, 'side_buttons_stack'):
            self.side_buttons_stack.setVisible(True)
            
            # Apply hidden mode and color mode to side buttons
            # We apply to all potential groups to ensure consistent state
            groups = []
            if hasattr(self, 'image_side_buttons'): groups.append(self.image_side_buttons)
            if hasattr(self, 'video_side_buttons'): groups.append(self.video_side_buttons)
            if hasattr(self, 'loop_side_buttons'): groups.append(self.loop_side_buttons)
            
            for group in groups:
                 if hasattr(group, 'set_hidden_mode'):
                     group.set_hidden_mode(should_hide_side, colored=should_be_colored)
                     
        # Update Main Mode Buttons (Max Size, Presets, Manual)
        if hasattr(self, 'mode_buttons'):
            self.mode_buttons.set_hidden_mode(should_hide_side)
    
    def set_lab_mode_active(self, active):
        """Set whether Lab mode is active (Lab button items selected)"""
        if self._lab_mode_active != active:
            self._lab_mode_active = active
            # Trigger visibility update WITHOUT emitting global_mode_changed
            current_tab = self.tabs.currentIndex()
            mode = self.tab_modes.get(current_tab, "Max Size")
            self._update_side_buttons_visibility(mode)
    
    def set_top_bar_preset_mode(self, active):
        """Set whether the top bar preset mode is active (controls side button visibility)"""
        if self._top_bar_preset_active != active:
            self._top_bar_preset_active = active
            # Trigger visibility update WITHOUT emitting global_mode_changed
            current_tab = self.tabs.currentIndex()
            mode = self.tab_modes.get(current_tab, "Max Size")
            self._update_side_buttons_visibility(mode)
    
    def _update_side_buttons_visibility(self, mode):
        """
        Update side buttons visibility based on lab mode and preset mode.
        This does NOT emit global_mode_changed to prevent signal collisions.
        """
        # Side Buttons visibility:
        # User Rule: Show ONLY when Lab Mode is ON (Lab button active) AND Top Bar Preset Mode is OFF
        should_hide_side = (not self._lab_mode_active) or self._top_bar_preset_active
        
        # User Rule: Colored ONLY in Lab Mode (Manual). Uncolored in Max Size.
        should_be_colored = (mode == "Manual")
        
        if hasattr(self, 'side_buttons_stack'):
            self.side_buttons_stack.setVisible(True)
            
            # Apply hidden mode and color mode to side buttons
            groups = []
            if hasattr(self, 'image_side_buttons'): groups.append(self.image_side_buttons)
            if hasattr(self, 'video_side_buttons'): groups.append(self.video_side_buttons)
            if hasattr(self, 'loop_side_buttons'): groups.append(self.loop_side_buttons)
            
            for group in groups:
                 if hasattr(group, 'set_hidden_mode'):
                     group.set_hidden_mode(should_hide_side, colored=should_be_colored)
                     
        # Update Main Mode Buttons (Max Size, Presets, Manual)
        if hasattr(self, 'mode_buttons'):
            self.mode_buttons.set_hidden_mode(should_hide_side)

    def _on_tab_changed(self, index):
        """Sync global mode buttons when tab changes"""
        mode = self.tab_modes.get(index, "Max Size")
        self.mode_buttons.blockSignals(True)
        self.mode_buttons.set_mode(mode)
        self.mode_buttons.blockSignals(False)
        
        # Sync side buttons stack
        if hasattr(self, 'side_buttons_stack'):
            self.side_buttons_stack.setCurrentIndex(index)
        
        # Update visibility based on mode
        is_presets = (mode == "Presets")
        if hasattr(self, 'side_buttons_stack'):
            self.side_buttons_stack.setVisible(not is_presets)
            
        # Update tab icons
        self.update_tab_icons()
        
        # Update GPU indicator for new tab
        self._update_gpu_indicator()

    def _update_image_transform_visibility(self, mode):
        """Show/hide image transform sections based on selected mode"""
        self.image_resize_container.setVisible(mode == 'resize')
        self.image_rotate_container.setVisible(mode == 'rotate')

    def _update_video_transform_visibility(self, mode):
        """Show/hide video transform/time sections based on selected mode"""
        self.video_resize_container.setVisible(mode == 'resize')
        self.video_rotate_container.setVisible(mode == 'rotate')
        self.video_time_container.setVisible(mode == 'time')

    def _update_loop_transform_visibility(self, mode):
        """Show/hide Loop transform/time sections based on selected mode"""
        self.gif_resize_container.setVisible(mode == 'resize')
        self.gif_rotate_container.setVisible(mode == 'rotate')
        self.gif_time_container.setVisible(mode == 'time')

    def mousePressEvent(self, event):
        """Clicking empty canvas should clear focus and focus active tab"""
        super().mousePressEvent(event)
        child = self.childAt(event.position().toPoint())
        if child is None or child == self:
            self._focus_active_tab()
    
    def _create_mode_separator(self):
        """Create a grey separator line to divide Mode section from parameters"""
        from PySide6.QtWidgets import QFrame
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setStyleSheet("background-color: #555555; margin: 4px 0px;")
        separator.setFixedHeight(1)
        return separator
    
    def _create_presets_section(self, prefix):
        """Create the social media and aspect ratio presets UI for a tab"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(12)
        
        # Social Media Buttons Row
        social_button_row = SquareButtonRow()

        
        social_group = QButtonGroup(self)
        social_group.setExclusive(True)
        
        platforms = [
            ("Instagram", "client/assets/icons/insta.svg"),
            ("X", "client/assets/icons/X_icon.svg"),
            ("LinkedIn", "client/assets/icons/in.svg"),
            ("YouTube", "client/assets/icons/yt.svg"),
            ("TikTok", "client/assets/icons/tik.svg"),
            ("Behance", "client/assets/icons/be.svg")
        ]
        
        for name, icon_path in platforms:
            btn = PresetButton(name, icon_path)
            btn.update_theme(self.is_dark_mode)
            social_group.addButton(btn)
            social_button_row.addButton(btn)
            # Store buttons for later reference if needed
            setattr(self, f"{prefix}_preset_{name.lower()}_btn", btn)
            
        layout.addWidget(social_button_row)
        
        # Connect signal to handler
        social_group.buttonClicked.connect(lambda btn: self.on_social_preset_changed(prefix, btn))
        
        # Ratios Label
        ratio_label = QLabel("Aspect Ratios")
        ratio_label.setStyleSheet("font-weight: bold; color: #AAAAAA; font-size: 11px;")
        layout.addWidget(ratio_label)
        
        # Ratio Buttons Row
        ratio_button_row = SquareButtonRow()
        
        ratio_group = QButtonGroup(self)
        ratio_group.setExclusive(True)
        
        ratios = [
            ("1:1", "client/assets/icons/11.svg"),
            ("3:4", "client/assets/icons/34.svg"),
            ("16:9", "client/assets/icons/169.svg"),
            ("9:16", "client/assets/icons/916.svg")
        ]
        
        for ratio, icon_path in ratios:
            btn = PresetButton(ratio, icon_path)
            btn.update_theme(self.is_dark_mode)
            ratio_group.addButton(btn)
            ratio_button_row.addButton(btn)
            # Store buttons for later reference if needed
            setattr(self, f"{prefix}_preset_ratio_{ratio.replace(':', '_')}_btn", btn)
            
        layout.addWidget(ratio_button_row)
        
        # Background Style (Video Only)
        if prefix == 'video':
            style_label = QLabel("Background Style")
            style_label.setStyleSheet("font-weight: bold; color: #AAAAAA; font-size: 11px;")
            self.video_bg_style_label = style_label
            
            self.video_bg_style = CustomComboBox()
            self.video_bg_style.addItems([BG_STYLE_BLACK_BARS, BG_STYLE_BLURRED, BG_STYLE_FILL_ZOOM])
            self.video_bg_style.setToolTip(
                "Upscaling ensures Instagram uses its high-quality player.\n"
                "Blurred backgrounds prevent 'dead space' on mobile screens."
            )
            
            # Initially hidden
            self.video_bg_style_label.setVisible(False)
            self.video_bg_style.setVisible(False)
            
            layout.addWidget(self.video_bg_style_label)
            layout.addWidget(self.video_bg_style)
            
            # Defaults: Instagram + 3:4
            for btn in social_group.buttons():
                if btn.text() == "Instagram":
                    btn.setChecked(True)
                    self.on_social_preset_changed(prefix, btn)
                    break
                    
            for btn in ratio_group.buttons():
                if btn.text() == "3:4":
                    btn.setChecked(True)
                    break

        # Store groups
        setattr(self, f"{prefix}_social_group", social_group)
        setattr(self, f"{prefix}_ratio_group", ratio_group)
        

        layout.addStretch()
        
        container.setVisible(False) # Hidden by default
        return container

    def on_social_preset_changed(self, prefix, btn):
        """Handle changes to social preset selection"""
        if prefix == 'video':
            # Check if Instagram is selected
            is_instagram = btn.text() == "Instagram"
            
            # Toggle visibility of Background Style
            if hasattr(self, 'video_bg_style'):
                self.video_bg_style.setVisible(is_instagram)
                self.video_bg_style_label.setVisible(is_instagram)
                
            # Auto-select 9:16 for Instagram if no ratio selected? 
            # Existing logic in conversion engine handles default ratio.
            # But UI might want to reflect it. For now, leave as is.

    def _get_checked_button_text(self, group):
        """Get the text or preset name of the checked button in a QButtonGroup"""
        checked = group.checkedButton()
        if not checked:
            return None
        if hasattr(checked, 'preset_name'):
            return checked.preset_name
        return checked.text()

    def _create_debug_spacer(self, number):
        """Create a spacer for gaps between sections"""
        # DEBUG: Colored spacers - COMMENTED OUT
        # colors = {
        #     1: "rgba(255, 0, 0, 200)", 2: "rgba(255, 128, 0, 200)", 3: "rgba(255, 255, 0, 200)",
        #     4: "rgba(0, 255, 0, 200)", 5: "rgba(0, 255, 255, 200)", 6: "rgba(0, 128, 255, 200)",
        #     7: "rgba(128, 0, 255, 200)", 8: "rgba(255, 0, 255, 200)", 9: "rgba(255, 192, 203, 200)",
        # }
        spacer = QWidget()
        spacer.setFixedHeight(8)
        # DEBUG: Uncomment to show colored spacers
        # spacer.setStyleSheet(f"background-color: {colors.get(number, 'rgba(128, 128, 128, 200)')};")
        # label = QLabel(f"{number}-GAP-8px", spacer)
        # label.setStyleSheet("color: black; font-size: 9px; font-weight: bold; background: rgba(255,255,255,180); padding: 1px;")
        # label.move(2, -1)
        return spacer
        
    def create_image_tab(self):
        """Create image conversion options tab"""
        # Feature flag: Use new extracted ImageTab component
        if USE_NEW_IMAGE_TAB:
            return self._create_image_tab_new()
        return self._create_image_tab_legacy()
    
    def _create_image_tab_new(self):
        """Create image tab using new extracted ImageTab component"""
        from client.gui.tabs import ImageTab
        
        # Create new ImageTab instance
        self._image_tab_component = ImageTab(
            parent=self,
            focus_callback=self._focus_active_tab
        )
        
        # Sync references for compatibility with existing code
        # These aliases allow existing code to access controls without modification
        self.image_format = self._image_tab_component.format
        self.image_quality = self._image_tab_component.quality
        self.image_quality_label = self._image_tab_component.quality_label
        self.image_quality_row_label = self._image_tab_component.quality_row_label
        self.multiple_qualities = self._image_tab_component.multiple_qualities
        self.quality_variants = self._image_tab_component.quality_variants
        self.quality_variants_label = self._image_tab_component.quality_variants_label
        self.image_max_size_spinbox = self._image_tab_component.max_size_spinbox
        self.image_max_size_label = self._image_tab_component.max_size_label
        self.image_auto_resize_checkbox = self._image_tab_component.auto_resize_checkbox
        self.image_resize_mode = self._image_tab_component.resize_mode
        self.resize_value = self._image_tab_component.resize_value
        self.resize_value_label = self._image_tab_component.resize_value_label
        self.multiple_resize = self._image_tab_component.multiple_resize
        self.resize_variants = self._image_tab_component.resize_variants
        self.resize_variants_label = self._image_tab_component.resize_variants_label
        self.image_rotation_angle = self._image_tab_component.rotation_angle
        self.image_resize_container = self._image_tab_component.resize_container
        self.image_rotate_container = self._image_tab_component.rotate_container
        self.image_format_group = self._image_tab_component.format_group
        self.image_transform_group = self._image_tab_component.transform_group
        
        # Create side buttons (still managed by CommandPanel)
        self.image_side_buttons = self._create_transform_side_buttons('image')
        self.image_side_buttons.selectionChanged.connect(
            lambda mode: self._image_tab_component.set_transform_mode(mode)
        )
        
        # Create presets section (managed by CommandPanel, added to format group)
        self.image_presets_section = self._create_presets_section("image")
        self._image_tab_component.format_group.add_row(self.image_presets_section)
        
        # Store mode value for compatibility
        self.image_size_mode_value = "max_size"
        
        return self._image_tab_component
    
    def create_video_tab(self):
        
        # Target Size - FIRST
        self.image_max_size_spinbox = CustomTargetSizeSpinBox(
            default_value=0.2,
            on_enter_callback=self._focus_active_tab
        )
        self.image_max_size_spinbox.setRange(0.01, 100.0)
        self.image_max_size_spinbox.setDecimals(2)
        self.image_max_size_spinbox.setSensitivity(0.0025)
        self.image_max_size_spinbox.setToolTip("Target maximum file size in megabytes")
        self.image_max_size_spinbox.setVisible(False)
        self.image_max_size_label = QLabel("Max Size")
        self.image_max_size_label.setVisible(False)
        self.image_format_group.add_row(self.image_max_size_label, self.image_max_size_spinbox)
        
        # Auto-resize checkbox
        self.image_auto_resize_checkbox = ThemedCheckBox("Auto-resize")
        self.image_auto_resize_checkbox.setChecked(True)
        self.image_auto_resize_checkbox.setToolTip(
            "Change the resolution in pixels (width×height) to match desired file size in MB."
        )
        self.image_auto_resize_checkbox.setVisible(False)
        self.image_format_group.add_row(self.image_auto_resize_checkbox)
        
        # Format buttons - FIRST
        self.image_format = FormatButtonRow(["WebP", "JPG", "PNG"])
        # Insert at the very top (index 0)
        self.image_format_group.get_content_layout().insertRow(0, self.image_format)


        # Multiple qualities option
        self.multiple_qualities = ThemedCheckBox("Multiple qualities")
        self.multiple_qualities.toggled.connect(self.toggle_quality_mode)
        self.image_format_group.add_row(self.multiple_qualities)
        
        # Quality settings
        self.image_quality = QSlider(Qt.Orientation.Horizontal)
        self.image_quality.setRange(1, 100)
        self.image_quality.setValue(40)
        self.image_quality_label = QLabel("40")
        self.image_quality.valueChanged.connect(lambda v: self.image_quality_label.setText(str(v)))
        
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(self.image_quality)
        quality_layout.addWidget(self.image_quality_label)
        self.image_quality_row_label = QLabel("Quality")
        self.image_format_group.add_row(self.image_quality_row_label, quality_layout)
        
        # Quality variants input
        self.quality_variants = QLineEdit()
        self.quality_variants.setPlaceholderText("e.g., 40, 60, 80, 95")
        self.quality_variants.setText("40, 60, 80, 95")
        self.quality_variants.setVisible(False)
        self.quality_variants_label = QLabel("Quality variants")
        self.quality_variants_label.setVisible(False)
        self.image_format_group.add_row(self.quality_variants_label, self.quality_variants)
        
        # Add presets section to group
        self.image_presets_section = self._create_presets_section("image")
        self.image_format_group.add_row(self.image_presets_section)

        # ============================================================
        # TRANSFORM FOLDER (Bottom) - with side buttons
        # ============================================================
        transform_row = QWidget()
        transform_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        transform_h = QHBoxLayout(transform_row)
        transform_h.setContentsMargins(0, 0, 0, 0)
        transform_h.setSpacing(0)
        
        # Side Buttons (Resize, Rotate)
        self.image_side_buttons = self._create_transform_side_buttons('image')
        self.image_side_buttons.selectionChanged.connect(self._update_image_transform_visibility)
        # Note: Added to global stack in setup_ui
        
        # Transform CommandGroup - expands to fill remaining width
        self.image_transform_group = CommandGroup("")
        self.image_transform_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.image_transform_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        self.image_transform_group.get_content_layout().setVerticalSpacing(12)
        self.image_transform_group.setFixedHeight(198)
        transform_h.addWidget(self.image_transform_group, 1)  # stretch=1 ensures it fills
        
        layout.addWidget(transform_row)
        
        # === RESIZE SECTION CONTAINER ===
        self.image_resize_container = QWidget()
        resize_layout = QVBoxLayout(self.image_resize_container)
        resize_layout.setContentsMargins(0, 0, 0, 0)
        resize_layout.setSpacing(8)
        
        # Resize widgets
        self.image_resize_mode = CustomComboBox()
        self.image_resize_mode.addItems(["No resize", "By width (pixels)", "By longer edge (pixels)", "By ratio (percent)"])
        self.image_resize_mode.setStyleSheet(COMBOBOX_STYLE)
        self.image_resize_mode.currentTextChanged.connect(self.on_image_resize_ui_changed)
        resize_layout.addWidget(self.image_resize_mode)
        
        self.multiple_resize = ThemedCheckBox("Multiple resize variants")
        self.multiple_resize.toggled.connect(self.toggle_resize_mode)
        resize_layout.addWidget(self.multiple_resize)
        
        # Single value row
        single_val_row = QHBoxLayout()
        self.resize_value_label = QLabel("Width (pixels)")
        self.resize_value = CustomSpinBox(on_enter_callback=self._focus_active_tab)
        self.resize_value.setRange(1, 10000)
        self.resize_value.setValue(720)
        single_val_row.addWidget(self.resize_value_label)
        single_val_row.addWidget(self.resize_value)
        resize_layout.addLayout(single_val_row)
        
        # Variants row
        variants_row = QHBoxLayout()
        self.resize_variants_label = QLabel("Resize values")
        self.resize_variants = QLineEdit()
        self.resize_variants.setPlaceholderText("e.g., 30,50,80 or 720,1280,1920")
        self.resize_variants.setText("720,1280,1920")
        variants_row.addWidget(self.resize_variants_label)
        variants_row.addWidget(self.resize_variants)
        resize_layout.addLayout(variants_row)
        
        # Initial visibility for sub-widgets
        self.resize_value_label.setVisible(False)
        self.resize_value.setVisible(False)
        self.resize_variants_label.setVisible(False)
        self.resize_variants.setVisible(False)
        
        self.image_transform_group.add_row(self.image_resize_container)
        
        # === ROTATION SECTION CONTAINER ===
        self.image_rotate_container = QWidget()
        rotate_layout = QVBoxLayout(self.image_rotate_container)
        rotate_layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_rotation_angle = RotationButtonRow()
        rotate_layout.addWidget(self.image_rotation_angle)
        
        self.image_transform_group.add_row(self.image_rotate_container)
        
        return tab
        
    def create_video_tab(self):
        """Create video conversion options tab"""
        # Feature flag: Use new extracted VideoTab component
        if USE_NEW_VIDEO_TAB:
            return self._create_video_tab_new()
        return self._create_video_tab_legacy()
    
    def _create_video_tab_new(self):
        """Create video tab using new extracted VideoTab component"""
        from client.gui.tabs import VideoTab
        
        # Create new VideoTab instance
        self._video_tab_component = VideoTab(
            parent=self,
            focus_callback=self._focus_active_tab,
            is_dark_mode=self.is_dark_mode
        )
        
        # Sync references for compatibility with existing code
        # These aliases allow existing code to access controls without modification
        self.video_codec = self._video_tab_component.codec
        self.video_codec_group = self._video_tab_component.codec_group
        self.video_max_size_spinbox = self._video_tab_component.max_size_spinbox
        self.video_max_size_label = self._video_tab_component.max_size_label
        self.video_auto_resize_checkbox = self._video_tab_component.auto_resize_checkbox
        self.multiple_video_qualities = self._video_tab_component.multiple_qualities
        self.video_quality = self._video_tab_component.quality
        self.video_quality_label = self._video_tab_component.quality_label
        self.video_quality_value = self._video_tab_component.quality_value
        self.video_quality_variants = self._video_tab_component.quality_variants
        self.video_quality_variants_label = self._video_tab_component.quality_variants_label
        self.video_resize_mode = self._video_tab_component.resize_mode
        self.multiple_video_variants = self._video_tab_component.multiple_variants
        self.video_resize_value = self._video_tab_component.resize_value
        self.video_resize_value_label = self._video_tab_component.resize_value_label
        self.video_size_variants = self._video_tab_component.size_variants
        self.video_size_variants_label = self._video_tab_component.size_variants_label
        self.video_rotation_angle = self._video_tab_component.rotation_angle
        self.video_resize_container = self._video_tab_component.resize_container
        self.video_rotate_container = self._video_tab_component.rotate_container
        self.video_time_container = self._video_tab_component.time_container
        self.video_transform_group = self._video_tab_component.transform_group
        self.enable_time_cutting = self._video_tab_component.enable_time_cutting
        self.time_range_slider = self._video_tab_component.time_range_slider
        self.enable_retime = self._video_tab_component.enable_retime
        self.retime_slider = self._video_tab_component.retime_slider
        self.retime_value_label = self._video_tab_component.retime_value_label
        
        # Create side buttons (still managed by CommandPanel)
        self.video_side_buttons = self._create_transform_side_buttons('video')
        self.video_side_buttons.selectionChanged.connect(
            lambda mode: self._video_tab_component.set_transform_mode(mode)
        )
        
        # Create presets section (managed by CommandPanel, added to codec group)
        self.video_presets_section = self._create_presets_section("video")
        self._video_tab_component.codec_group.add_row(self.video_presets_section)
        
        # Store mode value for compatibility
        self.video_size_mode_value = "max_size"
        
        # Connect codec change handler for GPU indicator
        self.video_codec.codecChanged.connect(self.on_video_codec_changed)
        
        return self._video_tab_component
    
    def create_loop_tab(self):
        
        # ============================================================
        # SETTINGS FOLDER (Top) - with invisible spacer to align with transform
        # ============================================================
        settings_row = QWidget()
        settings_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        settings_h = QHBoxLayout(settings_row)
        settings_h.setContentsMargins(0, 0, 0, 0)
        settings_h.setSpacing(0)
        
        # Settings CommandGroup - expands to fill remaining width
        codec_group = CommandGroup("")
        codec_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        codec_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        codec_group.setMinimumHeight(180)
        settings_h.addWidget(codec_group, 1)  # stretch=1 ensures it fills
        
        layout.addWidget(settings_row)
        
        # Removed local mode buttons, now handled globally
        self.video_size_mode_value = "max_size"
        
        # Target Size - FIRST (shown in Max Size mode)
        self.video_max_size_spinbox = CustomTargetSizeSpinBox(
            default_value=1.0,
            on_enter_callback=self._focus_active_tab
        )
        self.video_max_size_spinbox.setToolTip("Target maximum file size in megabytes")
        self.video_max_size_spinbox.setVisible(False)
        self.video_max_size_label = QLabel("Max Size")
        self.video_max_size_label.setVisible(False)
        codec_group.add_row(self.video_max_size_label, self.video_max_size_spinbox)

        # Auto-resize checkbox (for Max Size mode)
        self.video_auto_resize_checkbox = ThemedCheckBox("Auto-resize")
        self.video_auto_resize_checkbox.setChecked(True)
        self.video_auto_resize_checkbox.setToolTip(
            "Change the resolution in pixels (width×height) to match desired file size in MB."
        )
        self.video_auto_resize_checkbox.setVisible(False)
        codec_group.add_row(self.video_auto_resize_checkbox)
        
        # Format buttons - FIRST (Top of list)
        self.video_codec = VideoCodecSelector()
        self.video_codec.codecChanged.connect(self.on_video_codec_changed)
        
        # Insert at the very top (index 0)
        codec_group.get_content_layout().insertRow(0, self.video_codec)

        # Quality (CRF) slider for WebM
        self.video_quality = QSlider(Qt.Orientation.Horizontal)
        self.video_quality.setRange(0, 100)
        self.video_quality.setValue(30)  # Maps to CRF 23 (good quality)
        self.video_quality.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.video_quality.setTickInterval(10)
        self.video_quality.setToolTip("Quality: 0=lossless, 100=worst quality\nRecommended: 30-50 for WebM")
        self.video_quality_label = QLabel("Quality")
        self.video_quality_value = QLabel("30")
        self.video_quality.valueChanged.connect(lambda v: self.video_quality_value.setText(str(v)))
        
        # Create horizontal layout for slider and value display
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(self.video_quality)
        quality_layout.addWidget(self.video_quality_value)
        
        # Multiple video quality variants option - ABOVE slider
        self.multiple_video_qualities = ThemedCheckBox("Multiple quality variants")
        self.multiple_video_qualities.toggled.connect(self.toggle_video_quality_mode)
        codec_group.add_row(self.multiple_video_qualities)
        
        # Quality controls
        codec_group.add_row(self.video_quality_label, quality_layout)
        
        # Video quality variant inputs (hidden by default)
        self.video_quality_variants = QLineEdit()
        self.video_quality_variants.setPlaceholderText("e.g., 25,40,70 (quality values 0-100)")
        self.video_quality_variants.setText("15,23,31")
        self.video_quality_variants.setVisible(False)
        self.video_quality_variants.editingFinished.connect(self.validate_video_quality_variants)
        self.video_quality_variants_label = QLabel("Quality variants")
        self.video_quality_variants_label.setVisible(False)
        codec_group.add_row(self.video_quality_variants_label, self.video_quality_variants)
        
        # Presets section (initially hidden)
        self.video_presets_section = self._create_presets_section("video")
        codec_group.add_row(self.video_presets_section)

        # Set initial state for bitrate and quality visibility
        self.on_video_codec_changed(self.video_codec.currentText())

        # ============================================================
        # TRANSFORM FOLDER (Bottom) - with side buttons
        # ============================================================
        transform_row = QWidget()
        transform_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        transform_h = QHBoxLayout(transform_row)
        transform_h.setContentsMargins(0, 0, 0, 0)
        transform_h.setSpacing(0)
        
        # Side Buttons (Resize, Rotate, Time)
        self.video_side_buttons = self._create_transform_side_buttons('video')
        self.video_side_buttons.selectionChanged.connect(self._update_video_transform_visibility)
        # Note: Added to global stack in setup_ui
        
        # Transform CommandGroup - expands to fill remaining width
        self.video_transform_group = CommandGroup("")
        self.video_transform_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.video_transform_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        self.video_transform_group.get_content_layout().setVerticalSpacing(12)
        self.video_transform_group.setFixedHeight(198)
        transform_h.addWidget(self.video_transform_group, 1)  # stretch=1 ensures it fills
        
        layout.addWidget(transform_row)
        
        # === RESIZE SECTION CONTAINER ===
        self.video_resize_container = QWidget()
        resize_layout = QVBoxLayout(self.video_resize_container)
        resize_layout.setContentsMargins(0, 0, 0, 0)
        resize_layout.setSpacing(8)
        
        self.video_resize_mode = CustomComboBox()
        self.video_resize_mode.addItems(["No resize", "By width (pixels)", "By longer edge (pixels)", "By ratio (percent)"])
        self.video_resize_mode.setStyleSheet(COMBOBOX_STYLE)
        self.video_resize_mode.currentTextChanged.connect(self.on_video_resize_ui_changed)
        resize_layout.addWidget(self.video_resize_mode)
        
        self.multiple_video_variants = ThemedCheckBox("Multiple size variants")
        self.multiple_video_variants.toggled.connect(self.toggle_video_variant_mode)
        resize_layout.addWidget(self.multiple_video_variants)
        
        # Single value row
        single_val_row = QHBoxLayout()
        self.video_resize_value_label = QLabel("Width (pixels)")
        self.video_resize_value = CustomSpinBox(on_enter_callback=self._focus_active_tab)
        self.video_resize_value.setRange(1, 10000)
        self.video_resize_value.setValue(720)
        single_val_row.addWidget(self.video_resize_value_label)
        single_val_row.addWidget(self.video_resize_value)
        resize_layout.addLayout(single_val_row)
        
        # Variants row
        variants_row = QHBoxLayout()
        self.video_size_variants_label = QLabel("Size variants")
        self.video_size_variants = QLineEdit()
        self.video_size_variants.setPlaceholderText("e.g., 480,720,1080 or 25%,50%,75%")
        self.video_size_variants.setText("480,720,1280")
        variants_row.addWidget(self.video_size_variants_label)
        variants_row.addWidget(self.video_size_variants)
        resize_layout.addLayout(variants_row)

        # Initial visibility
        self.video_resize_value.setVisible(False)
        self.video_resize_value_label.setVisible(False)
        self.video_size_variants.setVisible(False)
        self.video_size_variants_label.setVisible(False)
        
        self.video_transform_group.add_row(self.video_resize_container)
        
        # === ROTATION SECTION CONTAINER ===
        self.video_rotate_container = QWidget()
        rotate_layout = QVBoxLayout(self.video_rotate_container)
        rotate_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_rotation_angle = RotationButtonRow()
        rotate_layout.addWidget(self.video_rotation_angle)
        
        self.video_transform_group.add_row(self.video_rotate_container)
        
        # === TIME SECTION CONTAINER ===
        self.video_time_container = QWidget()
        time_layout = QVBoxLayout(self.video_time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(12)
        
        # Time range row
        self.enable_time_cutting = ThemedCheckBox("Time range")
        self.enable_time_cutting.toggled.connect(self.toggle_time_cutting)
        
        self.time_range_slider = TimeRangeSlider(is_dark_mode=self.is_dark_mode)
        self.time_range_slider.setRange(0.0, 1.0)
        self.time_range_slider.setStartValue(0.0)
        self.time_range_slider.setEndValue(1.0)
        self.time_range_slider.setToolTip("Drag the handles to set start and end times (0% = beginning, 100% = end)")
        self.time_range_slider.setVisible(False)
        
        time_range_row = QHBoxLayout()
        time_range_row.addWidget(self.enable_time_cutting)
        time_range_row.addSpacing(8)
        time_range_row.addWidget(self.time_range_slider, 1)
        time_layout.addLayout(time_range_row)
        
        # Retime row
        self.enable_retime = ThemedCheckBox("Retime")
        self.enable_retime.toggled.connect(self.toggle_retime)
        
        self.retime_slider = QSlider(Qt.Orientation.Horizontal)
        self.retime_slider.setRange(10, 30)
        self.retime_slider.setValue(10)
        self.retime_slider.setSingleStep(1)
        self.retime_slider.setVisible(False)
        self.retime_value_label = QLabel("1.0x")
        self.retime_value_label.setVisible(False)
        self.retime_slider.valueChanged.connect(lambda v: self.retime_value_label.setText(f"{v/10:.1f}x"))
        
        retime_row = QHBoxLayout()
        retime_row.addWidget(self.enable_retime)
        retime_row.addSpacing(8)
        retime_row.addWidget(self.retime_slider, 1)
        retime_row.addWidget(self.retime_value_label)
        time_layout.addLayout(retime_row)
        
        self.video_transform_group.add_row(self.video_time_container)
        
        return tab
        
    def create_loop_tab(self):
        """Create Loop conversion options tab (GIF and WebM loop)"""
        # Feature flag: Use new extracted LoopTab component
        if USE_NEW_LOOP_TAB:
            return self._create_loop_tab_new()
        return self._create_loop_tab_legacy()
    
    def _create_loop_tab_new(self):
        """Create loop tab using new extracted LoopTab component"""
        from client.gui.tabs import LoopTab
        
        # Create new LoopTab instance
        self._loop_tab_component = LoopTab(
            parent=self,
            focus_callback=self._focus_active_tab,
            is_dark_mode=self.is_dark_mode
        )
        
        # Sync references for compatibility with existing code
        self.loop_format_selector = self._loop_tab_component.format_selector
        self.loop_format = self._loop_tab_component.format_selector  # Legacy alias
        self.ffmpeg_group = self._loop_tab_component.settings_group
        self.loop_max_size_spinbox = self._loop_tab_component.max_size_spinbox
        self.loop_max_size_label = self._loop_tab_component.max_size_label
        self.loop_auto_resize_checkbox = self._loop_tab_component.auto_resize_checkbox
        # Legacy aliases with gif_ prefix
        self.gif_max_size_spinbox = self._loop_tab_component.max_size_spinbox
        self.gif_max_size_label = self._loop_tab_component.max_size_label
        self.gif_auto_resize_checkbox = self._loop_tab_component.auto_resize_checkbox
        
        # GIF-specific
        self.gif_variants = self._loop_tab_component.gif_variants_checkbox
        self.gif_ffmpeg_variants = self._loop_tab_component.gif_variants_checkbox  # Legacy alias
        self.gif_fps = self._loop_tab_component.gif_fps
        self.gif_fps_label = self._loop_tab_component.gif_fps_label
        self.ffmpeg_gif_fps = self._loop_tab_component.gif_fps  # Legacy alias
        self.ffmpeg_gif_fps_label = self._loop_tab_component.gif_fps_label
        self.gif_fps_variants = self._loop_tab_component.gif_fps_variants
        self.gif_fps_variants_label = self._loop_tab_component.gif_fps_variants_label
        self.ffmpeg_gif_fps_variants = self._loop_tab_component.gif_fps_variants
        self.ffmpeg_gif_fps_variants_label = self._loop_tab_component.gif_fps_variants_label
        self.gif_colors = self._loop_tab_component.gif_colors
        self.gif_colors_label = self._loop_tab_component.gif_colors_label
        self.ffmpeg_gif_colors = self._loop_tab_component.gif_colors
        self.ffmpeg_gif_colors_label = self._loop_tab_component.gif_colors_label
        self.gif_colors_variants = self._loop_tab_component.gif_colors_variants
        self.gif_colors_variants_label = self._loop_tab_component.gif_colors_variants_label
        self.ffmpeg_gif_colors_variants = self._loop_tab_component.gif_colors_variants
        self.ffmpeg_gif_colors_variants_label = self._loop_tab_component.gif_colors_variants_label
        self.gif_dither_slider = self._loop_tab_component.gif_dither_slider
        self.gif_dither_value = self._loop_tab_component.gif_dither_value
        self.gif_dither_label = self._loop_tab_component.gif_dither_label
        self.ffmpeg_gif_dither = self._loop_tab_component.gif_dither_slider
        self.ffmpeg_gif_dither_value = self._loop_tab_component.gif_dither_value
        self.ffmpeg_gif_dither_label = self._loop_tab_component.gif_dither_label
        self.gif_dither_variants = self._loop_tab_component.gif_dither_variants
        self.gif_dither_variants_label = self._loop_tab_component.gif_dither_variants_label
        self.ffmpeg_gif_dither_variants = self._loop_tab_component.gif_dither_variants
        self.ffmpeg_gif_dither_variants_label = self._loop_tab_component.gif_dither_variants_label
        self.gif_blur = self._loop_tab_component.gif_blur
        self.ffmpeg_gif_blur = self._loop_tab_component.gif_blur
        
        # WebM-specific
        self.webm_variants = self._loop_tab_component.webm_variants_checkbox
        self.loop_webm_variants = self._loop_tab_component.webm_variants_checkbox  # Legacy alias
        self.webm_quality = self._loop_tab_component.webm_quality
        self.loop_webm_quality = self._loop_tab_component.webm_quality
        self.webm_quality_label = self._loop_tab_component.webm_quality_label
        self.loop_webm_quality_label = self._loop_tab_component.webm_quality_label
        self.webm_quality_value = self._loop_tab_component.webm_quality_value
        self.loop_webm_quality_value = self._loop_tab_component.webm_quality_value
        self.webm_quality_variants = self._loop_tab_component.webm_quality_variants
        self.loop_webm_quality_variants = self._loop_tab_component.webm_quality_variants
        self.webm_quality_variants_label = self._loop_tab_component.webm_quality_variants_label
        self.loop_webm_quality_variants_label = self._loop_tab_component.webm_quality_variants_label
        
        # Transform section - with both loop_ and gif_ prefixes for compatibility
        self.loop_resize_container = self._loop_tab_component.resize_container
        self.gif_resize_container = self._loop_tab_component.resize_container
        self.loop_rotate_container = self._loop_tab_component.rotate_container
        self.gif_rotate_container = self._loop_tab_component.rotate_container
        self.loop_time_container = self._loop_tab_component.time_container
        self.gif_time_container = self._loop_tab_component.time_container
        self.loop_transform_group = self._loop_tab_component.transform_group
        self.gif_transform_group = self._loop_tab_component.transform_group
        self.loop_resize_mode = self._loop_tab_component.resize_mode
        self.gif_resize_mode = self._loop_tab_component.resize_mode
        self.loop_resize_value = self._loop_tab_component.resize_value
        self.gif_resize_value = self._loop_tab_component.resize_value
        self.loop_resize_value_label = self._loop_tab_component.resize_value_label
        self.gif_resize_value_label = self._loop_tab_component.resize_value_label
        self.loop_multiple_resize = self._loop_tab_component.multiple_resize
        self.gif_multiple_resize = self._loop_tab_component.multiple_resize
        self.loop_resize_variants = self._loop_tab_component.resize_variants
        self.gif_resize_variants = self._loop_tab_component.resize_variants
        self.loop_resize_variants_label = self._loop_tab_component.resize_variants_label
        self.gif_resize_variants_label = self._loop_tab_component.resize_variants_label
        self.loop_rotation_angle = self._loop_tab_component.rotation_angle
        self.gif_rotation_angle = self._loop_tab_component.rotation_angle
        self.loop_enable_time_cutting = self._loop_tab_component.enable_time_cutting
        self.gif_enable_time_cutting = self._loop_tab_component.enable_time_cutting
        self.loop_time_range_slider = self._loop_tab_component.time_range_slider
        self.gif_time_range_slider = self._loop_tab_component.time_range_slider
        self.loop_enable_retime = self._loop_tab_component.enable_retime
        self.gif_enable_retime = self._loop_tab_component.enable_retime
        self.loop_retime_slider = self._loop_tab_component.retime_slider
        self.gif_retime_slider = self._loop_tab_component.retime_slider
        self.loop_retime_value_label = self._loop_tab_component.retime_value_label
        self.gif_retime_value_label = self._loop_tab_component.retime_value_label
        
        # Additional legacy aliases for specific widgets
        self.loop_webm_quality_row_label = self._loop_tab_component.webm_quality_label
        self.gif_dither_quality_slider = self._loop_tab_component.gif_dither_slider
        self.gif_dither_quality_label = self._loop_tab_component.gif_dither_value
        self.gif_dither_quality_row_label = self._loop_tab_component.gif_dither_label
        
        # Create side buttons (still managed by CommandPanel)
        self.loop_side_buttons = self._create_transform_side_buttons('gif')  # Keep 'gif' for legacy
        self.loop_side_buttons.selectionChanged.connect(
            lambda mode: self._loop_tab_component.set_transform_mode(mode)
        )
        
        # Create presets section (managed by CommandPanel, added to settings group)
        self.loop_presets_section = self._create_presets_section("loop")
        self.gif_presets_section = self._create_loop_presets_section()
        self._loop_tab_component.settings_group.add_row(self.loop_presets_section)
        self._loop_tab_component.settings_group.add_row(self.gif_presets_section)
        
        # Store mode value for compatibility
        self.loop_size_mode_value = "max_size"
        self.current_loop_preset = None
        
        # Connect format change handler
        self.loop_format_selector.formatChanged.connect(self.on_loop_format_changed)
        
        return self._loop_tab_component
    
    def _create_loop_tab_legacy(self):
        """Create loop tab using legacy inline code (original implementation)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.current_loop_preset = None # Tracks active preset for extra flags (e.g. tile-columns)
        
        # ============================================================
        # SETTINGS FOLDER (Top)
        # ============================================================
        settings_row = QWidget()
        settings_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        settings_h = QHBoxLayout(settings_row)
        settings_h.setContentsMargins(0, 0, 0, 0)
        settings_h.setSpacing(0)
        
        self.ffmpeg_group = CommandGroup("")
        self.ffmpeg_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ffmpeg_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        self.ffmpeg_group.setMinimumHeight(180)
        settings_h.addWidget(self.ffmpeg_group, 1)
        
        layout.addWidget(settings_row)
        
        self.loop_size_mode_value = "max_size"
        
        # Max Size
        self.gif_max_size_spinbox = CustomTargetSizeSpinBox(
            default_value=2.0,
            on_enter_callback=self._focus_active_tab
        )
        self.gif_max_size_spinbox.setToolTip("Target maximum file size in megabytes")
        self.gif_max_size_spinbox.setVisible(False)
        self.gif_max_size_label = QLabel("Max Size")
        self.gif_max_size_label.setVisible(False)
        self.ffmpeg_group.add_row(self.gif_max_size_label, self.gif_max_size_spinbox)
        
        # Auto-resize checkbox
        self.gif_auto_resize_checkbox = ThemedCheckBox("Auto-resize")
        self.gif_auto_resize_checkbox.setChecked(True)
        self.gif_auto_resize_checkbox.setVisible(False)
        self.ffmpeg_group.add_row(self.gif_auto_resize_checkbox)

        # Format Selector (FIRST Item) - Conditional panel with GIF/WebM toggle
        self.loop_format = LoopFormatSelector()
        self.loop_format.formatChanged.connect(self.on_loop_format_changed)
        self.ffmpeg_group.get_content_layout().insertRow(0, self.loop_format)

        # -- GIF Specific Widgets --
        
        self.gif_ffmpeg_variants = ThemedCheckBox("Multiple Variants (FPS, Colors, Qualities)")
        self.gif_ffmpeg_variants.toggled.connect(self.toggle_gif_ffmpeg_variants)
        self.ffmpeg_group.add_row(self.gif_ffmpeg_variants)
        
        # FPS
        self.ffmpeg_gif_fps = CustomComboBox()
        self.ffmpeg_gif_fps.addItems(["10", "12", "15", "18", "24"])
        self.ffmpeg_gif_fps.setCurrentText("15")
        self.ffmpeg_gif_fps_label = QLabel("FPS")
        self.ffmpeg_group.add_row(self.ffmpeg_gif_fps_label, self.ffmpeg_gif_fps)
        
        # FPS Variants
        self.ffmpeg_gif_fps_variants = QLineEdit()
        self.ffmpeg_gif_fps_variants.setPlaceholderText("e.g., 10,15,24")
        self.ffmpeg_gif_fps_variants.setVisible(False)
        self.ffmpeg_gif_fps_variants_label = QLabel("FPS variants")
        self.ffmpeg_gif_fps_variants_label.setVisible(False)
        self.ffmpeg_group.add_row(self.ffmpeg_gif_fps_variants_label, self.ffmpeg_gif_fps_variants)
        
        # Colors
        self.ffmpeg_gif_colors = CustomComboBox()
        self.ffmpeg_gif_colors.addItems(["8", "16", "32", "64", "128", "256"])
        self.ffmpeg_gif_colors.setCurrentText("256")
        self.ffmpeg_gif_colors_label = QLabel("Colors")
        self.ffmpeg_group.add_row(self.ffmpeg_gif_colors_label, self.ffmpeg_gif_colors)
        
        # Colors Variants
        self.ffmpeg_gif_colors_variants = QLineEdit()
        self.ffmpeg_gif_colors_variants.setPlaceholderText("e.g., 64,128,256")
        self.ffmpeg_gif_colors_variants.setVisible(False)
        self.ffmpeg_gif_colors_variants_label = QLabel("Colors variants")
        self.ffmpeg_gif_colors_variants_label.setVisible(False)
        self.ffmpeg_group.add_row(self.ffmpeg_gif_colors_variants_label, self.ffmpeg_gif_colors_variants)
        
        # Dither
        self.gif_dither_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.gif_dither_quality_slider.setRange(0, 5)
        self.gif_dither_quality_slider.setValue(3)
        self.gif_dither_quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.gif_dither_quality_slider.setTickInterval(1)
        self.gif_dither_quality_label = QLabel("3")
        self.gif_dither_quality_slider.valueChanged.connect(self.update_dither_quality_label)
        self.gif_dither_quality_row_label = QLabel("Quality")
        
        dither_layout = QHBoxLayout()
        dither_layout.addWidget(self.gif_dither_quality_slider)
        dither_layout.addWidget(self.gif_dither_quality_label)
        self.ffmpeg_group.add_row(self.gif_dither_quality_row_label, dither_layout)
        
        # Dither Variants
        self.ffmpeg_gif_dither_variants = QLineEdit()
        self.ffmpeg_gif_dither_variants.setPlaceholderText("e.g., 0,3,5")
        self.ffmpeg_gif_dither_variants.setVisible(False)
        self.ffmpeg_gif_dither_variants_label = QLabel("Quality variants (0-5)")
        self.ffmpeg_gif_dither_variants_label.setVisible(False)
        self.ffmpeg_group.add_row(self.ffmpeg_gif_dither_variants_label, self.ffmpeg_gif_dither_variants)
        
        # Blur
        self.ffmpeg_gif_blur = ThemedCheckBox("Reduce banding")
        self.ffmpeg_group.add_row(self.ffmpeg_gif_blur)

        # -- WebM Specific Widgets (Hidden by default) --
        
        # WebM multi-variant toggle
        self.loop_webm_variants = ThemedCheckBox("Multiple quality variants")
        self.loop_webm_variants.toggled.connect(self.on_loop_format_changed)
        self.loop_webm_variants.setVisible(False)
        self.ffmpeg_group.add_row(self.loop_webm_variants)
        
        # WebM Quality Slider (single value)
        self.loop_webm_quality = QSlider(Qt.Orientation.Horizontal)
        self.loop_webm_quality.setRange(0, 63)
        self.loop_webm_quality.setValue(30)
        self.loop_webm_quality.setVisible(False)
        
        self.loop_webm_quality_value = QLabel("30")
        self.loop_webm_quality_value.setVisible(False)
        self.loop_webm_quality.valueChanged.connect(lambda v: self.loop_webm_quality_value.setText(str(v)))
        
        self.loop_webm_quality_row_label = QLabel("Quality")
        self.loop_webm_quality_row_label.setVisible(False)
        
        webm_qual_layout = QHBoxLayout()
        webm_qual_layout.addWidget(self.loop_webm_quality)
        webm_qual_layout.addWidget(self.loop_webm_quality_value)
        self.ffmpeg_group.add_row(self.loop_webm_quality_row_label, webm_qual_layout)
        
        # WebM Quality Variants (multi-value)
        self.loop_webm_quality_variants = QLineEdit()
        self.loop_webm_quality_variants.setPlaceholderText("e.g., 20,30,40")
        self.loop_webm_quality_variants.setVisible(False)
        self.loop_webm_quality_variants_label = QLabel("Quality variants")
        self.loop_webm_quality_variants_label.setVisible(False)
        self.ffmpeg_group.add_row(self.loop_webm_quality_variants_label, self.loop_webm_quality_variants)

        # Presets (Shared)
        # Presets (Shared)
        self.gif_presets_section = self._create_loop_presets_section()
        self.ffmpeg_group.add_row(self.gif_presets_section)
        
        # ============================================================
        # TRANSFORM FOLDER
        # ============================================================
        transform_row = QWidget()
        transform_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        transform_h = QHBoxLayout(transform_row)
        transform_h.setContentsMargins(0, 0, 0, 0)
        transform_h.setSpacing(0)
        
        self.loop_side_buttons = self._create_transform_side_buttons('gif') # Keep ID 'gif' for now
        self.loop_side_buttons.selectionChanged.connect(self._update_loop_transform_visibility)
        
        self.gif_transform_group = CommandGroup("")
        self.gif_transform_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.gif_transform_group.get_content_layout().setContentsMargins(16, 16, 16, 16)
        self.gif_transform_group.get_content_layout().setVerticalSpacing(12)
        self.gif_transform_group.setFixedHeight(198)
        transform_h.addWidget(self.gif_transform_group, 1)
        
        layout.addWidget(transform_row)
        
        # Resize Container
        self.gif_resize_container = QWidget()
        resize_layout = QVBoxLayout(self.gif_resize_container)
        resize_layout.setContentsMargins(0, 0, 0, 0)
        resize_layout.setSpacing(8)
        
        self.gif_resize_mode = CustomComboBox()
        self.gif_resize_mode.addItems(["No resize", "By width (pixels)", "By longer edge (pixels)", "By ratio (percent)"])
        self.gif_resize_mode.setStyleSheet(COMBOBOX_STYLE)
        self.gif_resize_mode.currentTextChanged.connect(self.on_gif_resize_ui_changed)
        resize_layout.addWidget(self.gif_resize_mode)
        
        self.gif_multiple_resize = ThemedCheckBox("Multiple size variants")
        self.gif_multiple_resize.toggled.connect(self.toggle_gif_resize_variant_mode)
        resize_layout.addWidget(self.gif_multiple_resize)
        
        # Single value row
        single_val_row = QHBoxLayout()
        self.gif_resize_value_label = QLabel("Width (pixels)")
        self.gif_resize_value = CustomSpinBox(on_enter_callback=self._focus_active_tab)
        self.gif_resize_value.setRange(1, 10000)
        self.gif_resize_value.setValue(720)
        single_val_row.addWidget(self.gif_resize_value_label)
        single_val_row.addWidget(self.gif_resize_value)
        resize_layout.addLayout(single_val_row)
        
        # Variants row
        variants_row = QHBoxLayout()
        self.gif_resize_variants_label = QLabel("Size variants")
        self.gif_resize_variants = QLineEdit()
        self.gif_resize_variants.setPlaceholderText("e.g., 480,720,1080")
        self.gif_resize_variants.setText("480,720,1080")
        variants_row.addWidget(self.gif_resize_variants_label)
        variants_row.addWidget(self.gif_resize_variants)
        resize_layout.addLayout(variants_row)
        
        self.gif_resize_value.setVisible(False)
        self.gif_resize_value_label.setVisible(False)
        self.gif_resize_variants.setVisible(False)
        self.gif_resize_variants_label.setVisible(False)
        self.gif_transform_group.add_row(self.gif_resize_container)
        
        # Rotation
        self.gif_rotate_container = QWidget()
        rotate_layout = QVBoxLayout(self.gif_rotate_container)
        rotate_layout.setContentsMargins(0, 0, 0, 0)
        self.gif_rotation_angle = RotationButtonRow()
        rotate_layout.addWidget(self.gif_rotation_angle)
        self.gif_transform_group.add_row(self.gif_rotate_container)
        
        # Time
        self.gif_time_container = QWidget()
        time_layout = QVBoxLayout(self.gif_time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(12)
        
        self.gif_enable_time_cutting = ThemedCheckBox("Time range")
        self.gif_enable_time_cutting.toggled.connect(self.toggle_gif_time_cutting)
        
        self.gif_time_range_slider = TimeRangeSlider(is_dark_mode=self.is_dark_mode)
        self.gif_time_range_slider.setRange(0.0, 1.0)
        self.gif_time_range_slider.setStartValue(0.0)
        self.gif_time_range_slider.setEndValue(1.0)
        self.gif_time_range_slider.setVisible(False)
        
        time_row = QHBoxLayout()
        time_row.addWidget(self.gif_enable_time_cutting)
        time_row.addSpacing(8)
        time_row.addWidget(self.gif_time_range_slider, 1)
        time_layout.addLayout(time_row)
        
        self.gif_enable_retime = ThemedCheckBox("Retime")
        self.gif_enable_retime.toggled.connect(self.toggle_gif_retime)
        
        self.gif_retime_slider = QSlider(Qt.Orientation.Horizontal)
        self.gif_retime_slider.setRange(10, 30)
        self.gif_retime_slider.setValue(10)
        self.gif_retime_slider.setVisible(False)
        self.gif_retime_value_label = QLabel("1.0x")
        self.gif_retime_value_label.setVisible(False)
        self.gif_retime_slider.valueChanged.connect(lambda v: self.gif_retime_value_label.setText(f"{v/10:.1f}x"))
        
        retime_row = QHBoxLayout()
        retime_row.addWidget(self.gif_enable_retime)
        retime_row.addWidget(self.gif_retime_slider)
        retime_row.addWidget(self.gif_retime_value_label)
        time_layout.addLayout(retime_row)
        
        self.gif_transform_group.add_row(self.gif_time_container)
        
        # Initial call to set visibility
        self.on_loop_size_mode_changed("Max Size")
        
        return tab
        
    def _create_loop_presets_section(self):
        """Create specific presets for Loop tab (Hero, Alpha)"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        from collections import defaultdict
        groups = defaultdict(list)
        for name, config in LOOP_PRESETS.items():
            groups[config.get('row', 'Other')].append(name)
            
        # Group 1: Hero
        if 'Hero' in groups:
            hero_label = QLabel("Website Hero (WebM)")
            hero_label.setStyleSheet("font-weight: bold; color: #888;")
            layout.addWidget(hero_label)
            
            hero_row = SquareButtonRow()
            self.loop_preset_group = QButtonGroup(self) # Loop-specific exclusive group
            self.loop_preset_group.setExclusive(True)
            self.loop_preset_group.buttonClicked.connect(self.on_loop_preset_clicked)

            for name in groups['Hero']:
                btn = PresetButton(name) # Text only
                # Apply custom tooltip from config
                config = LOOP_PRESETS[name]
                btn.setToolTip(f"<b>{config.get('tooltip_title','')}</b><br>{config.get('tooltip_body','')}")
                install_app_tooltip(btn, btn.toolTip())
                
                btn.update_theme(self.is_dark_mode)
                self.loop_preset_group.addButton(btn)
                hero_row.addButton(btn)
            layout.addWidget(hero_row)
            
        # Group 2: Features (Alpha)
        if 'Features' in groups:
            feat_label = QLabel("Special Features")
            feat_label.setStyleSheet("font-weight: bold; color: #888; margin-top: 8px;")
            layout.addWidget(feat_label)
            
            feat_row = SquareButtonRow()
            for name in groups['Features']:
                btn = PresetButton(name)
                config = LOOP_PRESETS[name]
                btn.setToolTip(f"<b>{config.get('tooltip_title','')}</b><br>{config.get('tooltip_body','')}")
                install_app_tooltip(btn, btn.toolTip())

                btn.update_theme(self.is_dark_mode)
                self.loop_preset_group.addButton(btn) # Be part of same exclusive group? Yes, usually only one preset active.
                feat_row.addButton(btn)
            layout.addWidget(feat_row)
            
        return container

    def on_loop_preset_clicked(self, btn):
        """Apply Loop preset settings"""
        name = btn.text()
        if name not in LOOP_PRESETS:
            return
            
        config = LOOP_PRESETS[name]
        self.current_loop_preset = config
        
        # 1. Set Format
        format_type = config.get('format_type')
        if format_type == 'webm':
            codec = config.get('vcodec', '')
            if 'av1' in codec:
                self.loop_format.setCurrentText("WebM (AV1)")
            elif 'vp9' in codec:
                self.loop_format.setCurrentText("WebM (VP9)")
            else:
                 self.loop_format.setCurrentText("WebM")
                 
        # 2. Set Resize
        scale = config.get('scale') # e.g. "1280:720"
        if scale:
            width, height = scale.split(':')
            self.gif_resize_mode.setCurrentText("By width (pixels)")
            self.gif_resize_value.setValue(int(width))
            
        # 3. Set Quality (CRF)
        crf = config.get('crf')
        if crf:
            self.loop_webm_quality.setValue(int(crf))
        
    def on_loop_format_changed(self, format_name):
        """Handle Loop format change (GIF vs WebM)"""
        # Re-trigger size mode to update visibility based on new format
        self.on_loop_size_mode_changed(getattr(self, 'loop_size_mode_value', 'max_size').replace('_', ' ').title())
        # Update GPU indicator
        self._update_gpu_indicator()

    # NOTE: create_output_settings, create_control_buttons, on_convert_button_clicked,
    # set_conversion_state, stop_conversion, on_custom_output_toggled, browse_output_directory
    # have been removed - functionality moved to OutputFooter in main_window.py
            
    def get_conversion_params(self):
        """Get current conversion parameters"""
        current_tab = self.tabs.currentIndex()
        
        # Default output settings (will be overwritten by OutputFooter in main_window)
        params = {
            'output_dir': '',
            'use_nested_output': False,
            'nested_output_name': 'output',
            'suffix': '_converted',
            'overwrite': True,  # default overwrite when targeting output directory
        }
        
        if current_tab == 0:  # Images
            # Handle quality variants
            quality_variants = None
            if self.multiple_qualities.isChecked():
                variants_text = self.quality_variants.text().strip()
                if variants_text:
                    try:
                        quality_variants = [int(q.strip()) for q in variants_text.split(',') if q.strip().isdigit()]
                        quality_variants = [q for q in quality_variants if 1 <= q <= 100]  # Validate range
                    except:
                        quality_variants = None
            
            # Get resize values
            resize_values = self.get_resize_values()
            # If only one resize value, set as current_resize for single conversion
            current_resize = None
            if resize_values and len(resize_values) == 1:
                current_resize = resize_values[0]
            
            # Get size mode settings
            image_size_mode = getattr(self, 'image_size_mode_value', 'manual')
            
            params.update({
                'type': 'image',
                'format': self.image_format.currentText().lower(),
                'quality': self.image_quality.value(),
                'image_size_mode': image_size_mode,  # 'manual' or 'max_size'
                'image_max_size_mb': self.image_max_size_spinbox.value() if image_size_mode == 'max_size' else None,
                'image_auto_resize': self.image_auto_resize_checkbox.isChecked() if image_size_mode == 'max_size' else False,
                'quality_variants': quality_variants,
                'multiple_qualities': self.multiple_qualities.isChecked(),
                'resize_variants': resize_values,
                'current_resize': current_resize,
                'rotation_angle': self.image_rotation_angle.currentText(),
                'image_preset_social': self._get_checked_button_text(self.image_social_group),
                'image_preset_ratio': self._get_checked_button_text(self.image_ratio_group),
            })
        elif current_tab == 1:  # Videos
            # Handle video quality variants
            quality_variants = None
            if hasattr(self, 'multiple_video_qualities') and self.multiple_video_qualities.isChecked():
                variants_text = self.video_quality_variants.text().strip()
                if variants_text:
                    try:
                        quality_variants = [int(q.strip()) for q in variants_text.split(',') if q.strip().isdigit()]
                        quality_variants = [q for q in quality_variants if 0 <= q <= 100]  # Validate UI quality range
                    except:
                        quality_variants = None
            
            # Get video size mode settings
            video_size_mode = getattr(self, 'video_size_mode_value', 'manual')
            
            # Handle video size variants
            if hasattr(self, 'multiple_video_variants') and self.multiple_video_variants.isChecked():
                video_variants = self.get_video_variant_values()
                params.update({
                    'type': 'video',
                    'codec': self.video_codec.currentText(),
                    'quality': self.video_quality.value(),
                    'video_size_mode': video_size_mode,  # 'manual' or 'max_size'
                    'video_max_size_mb': self.video_max_size_spinbox.value() if video_size_mode == 'max_size' else None,
                    'video_auto_resize': self.video_auto_resize_checkbox.isChecked() if video_size_mode == 'max_size' else False,
                    'quality_variants': quality_variants,
                    'multiple_video_qualities': self.multiple_video_qualities.isChecked(),
                    'video_variants': video_variants,
                    'multiple_video_variants': True,
                    'rotation_angle': self.video_rotation_angle.currentText(),
                    'enable_time_cutting': self.enable_time_cutting.isChecked(),
                    'time_start': self.time_range_slider.getStartValue() if self.enable_time_cutting.isChecked() else 0.0,
                    'time_end': self.time_range_slider.getEndValue() if self.enable_time_cutting.isChecked() else 1.0,
                    'retime_enabled': self.enable_retime.isChecked(),
                    'retime_speed': self.retime_slider.value() / 10.0,
                    'video_preset_social': self._get_checked_button_text(self.video_social_group),
                    'video_preset_ratio': self._get_checked_button_text(self.video_ratio_group),
                    'video_background_style': self.video_bg_style.currentText() if hasattr(self, 'video_bg_style') and self.video_bg_style.isVisible() else None,
                })
            else:
                video_resize = self.get_video_resize_values()
                video_width = None
                video_scale = False
                if video_resize and len(video_resize) == 1:
                    v = video_resize[0]
                    if v.endswith('%'):
                        video_scale = True
                        video_width = v
                    else:
                        try:
                            video_width = int(v)
                            video_scale = True
                        except Exception:
                            video_width = None
                params.update({
                    'type': 'video',
                    'codec': self.video_codec.currentText(),
                    'quality': self.video_quality.value(),
                    'video_size_mode': video_size_mode,  # 'manual' or 'max_size'
                    'video_max_size_mb': self.video_max_size_spinbox.value() if video_size_mode == 'max_size' else None,
                    'video_auto_resize': self.video_auto_resize_checkbox.isChecked() if video_size_mode == 'max_size' else False,
                    'quality_variants': quality_variants,
                    'multiple_video_qualities': self.multiple_video_qualities.isChecked(),
                    'video_variants': [],
                    'multiple_video_variants': False,
                    'width': video_width,
                    'scale': video_scale,
                    'rotation_angle': self.video_rotation_angle.currentText(),
                    'enable_time_cutting': self.enable_time_cutting.isChecked(),
                    'time_start': self.time_range_slider.getStartValue() if self.enable_time_cutting.isChecked() else 0.0,
                    'time_end': self.time_range_slider.getEndValue() if self.enable_time_cutting.isChecked() else 1.0,
                    'retime_enabled': self.enable_retime.isChecked(),
                    'retime_speed': self.retime_slider.value() / 10.0,
                    'video_preset_social': self._get_checked_button_text(self.video_social_group),
                    'video_preset_ratio': self._get_checked_button_text(self.video_ratio_group),
                    'video_background_style': self.video_bg_style.currentText() if hasattr(self, 'video_bg_style') and self.video_bg_style.isVisible() else None,
                })
        elif current_tab == 2:  # Loop (GIF or WebM)
            # Determine format
            loop_format = self.loop_format.currentText()
            is_webm = "WebM" in loop_format
            
            # Use GIF resizing inputs for consistency in Loop tab for now
            loop_resize_values = self.get_gif_resize_values()
            
            # Common params
            params.update({
                'rotation': self.gif_rotation_angle.currentText(),
                'enable_time_cutting': self.gif_enable_time_cutting.isChecked(),
                'time_start': self.gif_time_range_slider.getStartValue() if self.gif_enable_time_cutting.isChecked() else 0.0,
                'time_end': self.gif_time_range_slider.getEndValue() if self.gif_enable_time_cutting.isChecked() else 1.0,
                'retime_enabled': self.gif_enable_retime.isChecked(),
                'retime_speed': self.gif_retime_slider.value() / 10.0,
                'gif_preset_social': None,
                'gif_preset_ratio': None,
            })
            
            if is_webm:
                # WebM Logic (using Loop tab widgets)
                # Use exact strings expected by ConversionEngine codec_map
                codec = "WebM (VP9, faster)" if "VP9" in loop_format else "WebM (AV1, slower)"
                
                # Check auto-resize/max size settings from the Loop tab widgets
                size_mode = getattr(self, 'loop_size_mode_value', 'max_size')
                
                # Map GIF resize logic to Video params
                # Width/Scale logic needs to be constructed from get_gif_resize_values result
                width = None
                scale = False
                if loop_resize_values and len(loop_resize_values) == 1:
                     v = loop_resize_values[0]
                     if v.endswith('%'):
                         scale = True
                         width = v
                     else:
                         try:
                             # L{value} or {value}
                             if v.startswith('L'):
                                 width = v.replace('L', '') # Treat as width?
                             else:
                                 width = int(v)
                                 scale = True
                         except:
                             pass

                webm_params = {
                    'type': 'video', 
                    'codec': codec,
                    'quality': self.loop_webm_quality.value(), # Use our new widget
                    'quality_variants': None, # Variants not implemented for Loop WebM yet
                    'multiple_video_qualities': False,
                    
                    # Map max size / auto resize
                    'video_size_mode': size_mode,
                    'video_max_size_mb': self.gif_max_size_spinbox.value() if size_mode == 'max_size' else None,
                    'video_auto_resize': self.gif_auto_resize_checkbox.isChecked() if size_mode == 'max_size' else False,
                    
                    # Map resize
                    'width': width,
                    'scale': scale,
                    
                    # Ensure video variants empty
                    'video_variants': [],
                    'multiple_video_variants': False
                }
                
                # Inject active Loop Preset overrides
                if self.current_loop_preset:
                    # Audio stripping
                    if self.current_loop_preset.get('an'):
                        webm_params['remove_audio'] = True
                        
                    # Pixel Format (Transparency)
                    if self.current_loop_preset.get('pix_fmt'):
                         webm_params['pix_fmt'] = self.current_loop_preset.get('pix_fmt')
                         
                    # Extra Arguments (Tile columns, Tune, Metadata)
                    extra_args = {}
                    if self.current_loop_preset.get('tile-columns'):
                         extra_args['tile-columns'] = self.current_loop_preset.get('tile-columns')
                    
                    if self.current_loop_preset.get('tune'):
                         extra_args['tune'] = self.current_loop_preset.get('tune')
                         
                    if self.current_loop_preset.get('metadata'):
                        for k, v in self.current_loop_preset.get('metadata').items():
                            extra_args[f"metadata:{k}"] = v
                            
                    if extra_args:
                         webm_params['extra_ffmpeg_args'] = extra_args

                    # Upscaling
                    if self.current_loop_preset.get('allow_upscaling'):
                         webm_params['allow_upscaling'] = True

                params.update(webm_params)
            else:
                # GIF Logic (Existing)
                gif_variants = self.get_gif_variant_values()
                size_mode = getattr(self, 'loop_size_mode_value', 'max_size')
                
                params.update({
                    'type': 'gif',
                    'use_ffmpeg_gif': True,
                    'gif_size_mode': size_mode,
                    'gif_max_size_mb': self.gif_max_size_spinbox.value() if size_mode == 'max_size' else None,
                    'gif_auto_resize': self.gif_auto_resize_checkbox.isChecked() if size_mode == 'max_size' else False,
                    'ffmpeg_fps': int(self.ffmpeg_gif_fps.currentText()),
                    'ffmpeg_colors': int(self.ffmpeg_gif_colors.currentText()),
                    'ffmpeg_dither': self.get_dither_string_from_quality(self.gif_dither_quality_slider.value()),
                    'ffmpeg_blur': self.ffmpeg_gif_blur.isChecked(),
                    'gif_resize_mode': self.gif_resize_mode.currentText(),
                    'gif_resize_values': loop_resize_values,
                    'gif_variants': gif_variants,
                    'multiple_gif_variants': bool(gif_variants),
                })
            
        return params
    
    # --- Mediator-Shell API Alias ---
    def get_parameters(self) -> dict:
        """
        Get current conversion parameters.
        
        Mediator-Shell API: This is the primary method for MainWindow
        to retrieve configuration from the CommandPanel.
        
        Returns:
            dict: Conversion parameters including type, format, quality, etc.
        """
        return self.get_conversion_params()
    
    def get_execution_payload(self) -> dict:
        """
        Get complete execution payload with all variants and rotation included.
        
        This method gathers ALL parameters needed for conversion, so MainWindow
        does not need to do any additional parameter gathering.
        
        Returns:
            dict: Complete conversion payload ready for ConversionEngine
        """
        params = self.get_conversion_params()
        current_tab = self.tabs.currentIndex()
        
        # Add resize variants based on active tab
        if current_tab == 0:  # Images Tab
            resize_variants = self.get_resize_values()
            if resize_variants:
                params['resize_variants'] = resize_variants
            # Add rotation
            if hasattr(self, 'image_rotation_angle'):
                rotation = self.image_rotation_angle.currentText()
                if rotation != "No rotation":
                    params['rotation_angle'] = rotation
                    
        elif current_tab == 1:  # Videos Tab
            video_variants = self.get_video_variant_values()
            if video_variants:
                params['video_variants'] = video_variants
            # Add rotation
            if hasattr(self, 'video_rotation_angle'):
                rotation = self.video_rotation_angle.currentText()
                if rotation != "No rotation":
                    params['rotation_angle'] = rotation
                    
        elif current_tab == 2:  # GIFs/Loop Tab
            # Add rotation
            if hasattr(self, 'gif_rotation_angle'):
                rotation = self.gif_rotation_angle.currentText()
                if rotation != "No rotation":
                    params['gif_rotation_angle'] = rotation
        
        return params
        
    def start_conversion(self):
        """Emit conversion request signal"""
        params = self.get_conversion_params()
        self.conversion_requested.emit(params)
        
    def preview_command(self):
        """Show preview of the command that would be executed"""
        params = self.get_conversion_params()
        
        # Create a simple preview dialog
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Command Preview")
        dialog.resize(600, 400)
        
        # Apply dark theme to the dialog
        from .theme_manager import ThemeManager
        theme = ThemeManager()
        dialog.setStyleSheet(theme.get_dialog_styles())
        
        layout = QVBoxLayout(dialog)
        
        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setPlainText(f"Conversion Parameters:\n{json.dumps(params, indent=2)}")
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        
        layout.addWidget(preview_text)
        layout.addWidget(close_btn)
        
        dialog.exec()
        
    def toggle_quality_mode(self, checked):
        """Toggle between single and multiple quality modes"""
        # Show/hide appropriate controls
        self.image_quality.setVisible(not checked)
        self.image_quality_label.setVisible(not checked)
        self.image_quality_row_label.setVisible(not checked)
        self.quality_variants.setVisible(checked)
        self.quality_variants_label.setVisible(checked)
    
    def toggle_resize_mode(self, checked):
        """Toggle between single and multiple resize modes"""
        # Show/hide appropriate controls
        self.resize_value.setVisible(not checked)
        self.resize_value_label.setVisible(not checked)
        self.resize_variants.setVisible(checked)
        self.resize_variants_label.setVisible(checked)
        
        # Update default values and placeholder based on current mode
        if checked:
            current_mode = self.image_resize_mode.currentText()
            # Auto-select "By longer edge" if currently "No resize"
            if current_mode == "No resize":
                self.image_resize_mode.setCurrentText("By longer edge (pixels)")
                current_mode = "By longer edge (pixels)"
            
            if current_mode == "By ratio (percent)":
                self.resize_variants.setPlaceholderText("e.g., 33,66,90")
                self.resize_variants.setText("33,66")
            else:
                self.resize_variants.setPlaceholderText("e.g., 720,1280,1920")
                self.resize_variants.setText("720,1280,1920")
        else:
            # Set single resize default based on mode
            current_mode = self.image_resize_mode.currentText()
            if current_mode == "By width (pixels)" or current_mode == "By longer edge (pixels)":
                if self.resize_value.value() != 720:
                    self.resize_value.setValue(720)
            elif current_mode == "By ratio (percent)":
                if self.resize_value.value() != 50:
                    self.resize_value.setValue(50)
    
    def on_resize_value_changed(self, value):
        """Save the current resize value based on the current mode"""
        current_mode = self.resize_mode.currentText()
        if current_mode == "By width (pixels)":
            self.last_pixel_value = value
        elif current_mode == "By ratio (percent)":
            self.last_percent_value = value
    
    def get_resize_values(self):
        """Get list of resize values from input - simplified version"""
        resize_mode = self.image_resize_mode.currentText()
        
        if resize_mode == "No resize":
            return []
            
        if hasattr(self, 'multiple_resize') and self.multiple_resize.isChecked():
            resize_text = self.resize_variants.text().strip()
            if not resize_text:
                return []
            
            # Simple split by comma and clean values
            values = []
            for value in resize_text.split(','):
                value = value.strip()
                if not value:
                    continue
                
                try:
                    if resize_mode == "By ratio (percent)":
                        # Validate percentage (1-200)
                        percent = float(value)
                        if 1 <= percent <= 200:
                            values.append(f"{percent}%")
                    elif resize_mode == "By longer edge (pixels)":
                        # Prefix with "L" for longer edge
                        width = int(value)
                        if width > 0:
                            values.append(f"L{width}")
                    else:  # By width (pixels)
                        # Validate pixel width (positive integer)
                        width = int(value)
                        if width > 0:
                            values.append(str(width))
                except (ValueError, TypeError):
                    continue  # Skip invalid values
            
            return values
        else:
            # Single resize mode - get value from input
            if resize_mode == "By ratio (percent)":
                value = self.resize_value.value() if hasattr(self, 'resize_value') else 100
                return [f"{value}%"]
            elif resize_mode == "By width (pixels)":
                value = self.resize_value.value() if hasattr(self, 'resize_value') else 1920
                return [str(value)]
            elif resize_mode == "By longer edge (pixels)":
                value = self.resize_value.value() if hasattr(self, 'resize_value') else 1920
                return [f"L{value}"]
            else:
                return []
    

    
    def toggle_gif_ffmpeg_variants(self, checked):
        """Toggle between single and multiple FFmpeg variant modes"""
        # Show/hide single controls
        self.ffmpeg_gif_fps.setVisible(not checked)
        self.ffmpeg_gif_fps_label.setVisible(not checked)
        self.ffmpeg_gif_colors.setVisible(not checked)
        self.ffmpeg_gif_colors_label.setVisible(not checked)
        # self.ffmpeg_gif_dither.setVisible(not checked)
        # self.ffmpeg_gif_dither_label.setVisible(not checked)
        self.gif_dither_quality_slider.setVisible(not checked)
        self.gif_dither_quality_row_label.setVisible(not checked)
        self.gif_dither_quality_label.setVisible(not checked)
        
        # Show/hide variant controls
        self.ffmpeg_gif_fps_variants.setVisible(checked)
        self.ffmpeg_gif_fps_variants_label.setVisible(checked)
        self.ffmpeg_gif_colors_variants.setVisible(checked)
        self.ffmpeg_gif_colors_variants_label.setVisible(checked)
        self.ffmpeg_gif_dither_variants.setVisible(checked)
        self.ffmpeg_gif_dither_variants_label.setVisible(checked)
        
        # Set default values if empty
        if checked:
            if not self.ffmpeg_gif_fps_variants.text():
                self.ffmpeg_gif_fps_variants.setText("10,15,24")
            if not self.ffmpeg_gif_colors_variants.text():
                self.ffmpeg_gif_colors_variants.setText("64,128,256")
            if not self.ffmpeg_gif_dither_variants.text():
                self.ffmpeg_gif_dither_variants.setText("0,3,5")

    def get_gif_variant_values(self):
        """Get all GIF variant values if multiple variants is enabled"""
        variants = {}
        
        # Check if resize variants are enabled
        if hasattr(self, 'gif_multiple_resize') and self.gif_multiple_resize.isChecked():
            resize_values = self.get_gif_resize_values()
            if resize_values:
                variants['resize'] = resize_values
        
        # Check if FFmpeg variants are enabled
        if hasattr(self, 'gif_ffmpeg_variants') and self.gif_ffmpeg_variants.isChecked():
            # FPS
            fps_text = self.ffmpeg_gif_fps_variants.text().strip()
            if fps_text:
                try:
                    fps_values = [int(x.strip()) for x in fps_text.split(',') if x.strip().isdigit()]
                    if fps_values:
                        variants['fps'] = fps_values
                except:
                    pass
            
            # Colors
            colors_text = self.ffmpeg_gif_colors_variants.text().strip()
            if colors_text:
                try:
                    colors_values = [int(x.strip()) for x in colors_text.split(',') if x.strip().isdigit()]
                    if colors_values:
                        variants['colors'] = colors_values
                except:
                    pass
            
            # Dither (Quality 0-5)
            dither_text = self.ffmpeg_gif_dither_variants.text().strip()
            if dither_text:
                try:
                    qualities = [int(x.strip()) for x in dither_text.split(',') if x.strip().isdigit()]
                    if qualities:
                        # Map qualities to dither strings
                        variants['dither'] = [self.get_dither_string_from_quality(q) for q in qualities if 0 <= q <= 5]
                except:
                    pass
        
        return variants

    def update_dither_quality_label(self, value):
        """Update dither quality label based on slider value"""
        self.gif_dither_quality_label.setText(str(value))

    def get_dither_string_from_quality(self, quality):
        """Map integer quality (0-5) to FFmpeg dither string"""
        mapping = {
            0: "none",
            1: "bayer:bayer_scale=5",
            2: "bayer:bayer_scale=4",
            3: "bayer:bayer_scale=3",
            4: "bayer:bayer_scale=1",
            5: "floyd_steinberg"
        }
        return mapping.get(quality, "floyd_steinberg")

    def on_gif_size_mode_changed(self, mode):
        """Handle GIF size mode change between Manual, Max Size, and Presets"""
        if mode not in ["Max Size", "Manual", "Presets"]:
            return

        is_max_size = (mode == "Max Size")
        is_manual = (mode == "Manual")
        is_presets = (mode == "Presets")
        
        self.gif_size_mode_value = mode.lower().replace(" ", "_")
        
        # Show/hide max size controls
        self.gif_max_size_label.setVisible(is_max_size)
        self.gif_max_size_spinbox.setVisible(is_max_size)
        self.gif_auto_resize_checkbox.setVisible(is_max_size)
        
        # Presets visibility
        self.gif_presets_section.setVisible(is_presets)

        # Transform and Time group visibility
        self.gif_transform_group.setVisible(not is_presets)
        self.gif_time_group.setVisible(not is_presets)
        # self.gif_size_estimate_label.setVisible(is_max_size)  # REMOVED - not in layout anymore
        
        if is_max_size or is_presets:
            # Hide manual quality controls in Max Size or Presets mode
            self.gif_ffmpeg_variants.setChecked(False)
            self.gif_ffmpeg_variants.setVisible(False)
            
            self.ffmpeg_gif_fps_label.setVisible(False)
            self.ffmpeg_gif_fps.setVisible(False)
            self.ffmpeg_gif_fps_variants_label.setVisible(False)
            self.ffmpeg_gif_fps_variants.setVisible(False)
            
            self.ffmpeg_gif_colors_label.setVisible(False)
            self.ffmpeg_gif_colors.setVisible(False)
            self.ffmpeg_gif_colors_variants_label.setVisible(False)
            self.ffmpeg_gif_colors_variants.setVisible(False)
            
            self.gif_dither_quality_slider.setVisible(False)
            self.gif_dither_quality_row_label.setVisible(False)
            self.gif_dither_quality_label.setVisible(False)
            self.ffmpeg_gif_dither_variants_label.setVisible(False)
            self.ffmpeg_gif_dither_variants.setVisible(False)
            
            self.gif_size_estimate_label.setText("")
            
            if is_presets:
                self.gif_resize_mode.setCurrentText("No resize")
        else:
            # Show manual controls in Manual mode
            self.gif_ffmpeg_variants.setVisible(True)
            
            self.ffmpeg_gif_fps_label.setVisible(True)
            self.ffmpeg_gif_fps.setVisible(True)
            
            self.ffmpeg_gif_colors_label.setVisible(True)
            self.ffmpeg_gif_colors.setVisible(True)
            
            self.gif_dither_quality_slider.setVisible(True)
            self.gif_dither_quality_row_label.setVisible(True)
            self.gif_dither_quality_label.setVisible(True)
            
            # Variants visibility depends on toggle state
            variants_enabled = self.gif_ffmpeg_variants.isChecked()
            self.ffmpeg_gif_fps_variants_label.setVisible(variants_enabled)
            self.ffmpeg_gif_fps_variants.setVisible(variants_enabled)
            self.ffmpeg_gif_colors_variants_label.setVisible(variants_enabled)
            self.ffmpeg_gif_colors_variants.setVisible(variants_enabled)
            self.ffmpeg_gif_dither_variants_label.setVisible(variants_enabled)
            self.ffmpeg_gif_dither_variants.setVisible(variants_enabled)
            
            self.gif_size_estimate_label.setText("")

    def on_image_resize_ui_changed(self, mode):
        """Handle Image resize dropdown change - update UI visibility only"""
        # Do not affect settings mode!
        # Uncheck multi-variant toggle if switching to "No resize"
        if mode == "No resize" and hasattr(self, 'multiple_resize') and self.multiple_resize.isChecked():
            self.multiple_resize.blockSignals(True)
            self.multiple_resize.setChecked(False)
            self.multiple_resize.blockSignals(False)
            # Manually trigger the toggle handler to update UI
            self.toggle_resize_mode(False)
        
        # Only show/hide resize input when not in "multiple variants" mode
        if hasattr(self, 'multiple_resize') and self.multiple_resize.isChecked():
            # Update multi-resize defaults when mode changes
            if mode == "By ratio (percent)":
                self.resize_variants.setPlaceholderText("e.g., 33,66,90")
                self.resize_variants.setText("33,66")
            elif mode in ["By width (pixels)", "By longer edge (pixels)"]:
                self.resize_variants.setPlaceholderText("e.g., 720,1280,1920")
                self.resize_variants.setText("720,1280,1920")
            return
            
        if mode == "No resize":
            self.resize_value.setVisible(False)
            self.resize_value_label.setVisible(False)
        else:
            self.resize_value.setVisible(True)
            self.resize_value_label.setVisible(True)
            
            if mode == "By width (pixels)":
                self.resize_value_label.setText("Width (pixels):")
                current_val = self.resize_value.value()
                self.resize_value.setRange(1, 10000)
                if current_val < 1 or current_val > 10000 or current_val == 50:
                    self.resize_value.setValue(720)
            elif mode == "By longer edge (pixels)":
                self.resize_value_label.setText("Longer edge (px):")
                current_val = self.resize_value.value()
                self.resize_value.setRange(1, 10000)
                if current_val < 1 or current_val > 10000 or current_val == 50:
                    self.resize_value.setValue(720)
            elif mode == "By ratio (percent)":
                self.resize_value_label.setText("Percentage:")
                # Check value BEFORE changing range (Qt clamps automatically)
                current_val = self.resize_value.value()
                self.resize_value.setRange(1, 200)
                if current_val < 1 or current_val > 200:
                    self.resize_value.setValue(50)

    def on_video_resize_ui_changed(self, mode):
        """Handle Video resize dropdown change - update UI visibility only"""
        # Do not affect settings mode!
        # Uncheck multi-variant toggle if switching to "No resize"
        if mode == "No resize" and hasattr(self, 'multiple_video_variants') and self.multiple_video_variants.isChecked():
            self.multiple_video_variants.blockSignals(True)
            self.multiple_video_variants.setChecked(False)
            self.multiple_video_variants.blockSignals(False)
            # Manually trigger the toggle handler to update UI
            self.toggle_video_variant_mode(False)
        
        # Only show/hide resize input when not in "multiple variants" mode
        if hasattr(self, 'multiple_video_variants') and self.multiple_video_variants.isChecked():
            # Update multi-resize defaults when mode changes
            if mode == "By ratio (percent)":
                self.video_size_variants.setPlaceholderText("e.g., 33,66,90")
                self.video_size_variants.setText("33,66")
            elif mode in ["By width (pixels)", "By longer edge (pixels)"]:
                self.video_size_variants.setPlaceholderText("e.g., 480,720,960")
                self.video_size_variants.setText("480,720,960")
            return
            
        if mode == "No resize":
            self.video_resize_value.setVisible(False)
            self.video_resize_value_label.setVisible(False)
        else:
            self.video_resize_value.setVisible(True)
            self.video_resize_value_label.setVisible(True)
            
            if mode == "By width (pixels)":
                self.video_resize_value_label.setText("Width (pixels):")
                current_val = self.video_resize_value.value()
                self.video_resize_value.setRange(1, 10000)
                if current_val < 1 or current_val > 10000 or current_val == 50:
                    self.video_resize_value.setValue(640)
            elif mode == "By longer edge (pixels)":
                self.video_resize_value_label.setText("Longer edge (px):")
                current_val = self.video_resize_value.value()
                self.video_resize_value.setRange(1, 10000)
                if current_val < 1 or current_val > 10000 or current_val == 50:
                    self.video_resize_value.setValue(640)
            elif mode == "By ratio (percent)":
                self.video_resize_value_label.setText("Percentage:")
                # Check value BEFORE changing range (Qt clamps automatically)
                current_val = self.video_resize_value.value()
                self.video_resize_value.setRange(1, 200)
                if current_val < 1 or current_val > 200:
                    self.video_resize_value.setValue(50)

    def on_gif_resize_ui_changed(self, mode):
        """Handle GIF resize dropdown change - update UI visibility only"""
        # Do not affect settings mode!
        # Uncheck multi-variant toggle if switching to "No resize"
        if mode == "No resize" and hasattr(self, 'gif_multiple_resize') and self.gif_multiple_resize.isChecked():
            # Uncheck the toggle and update UI
            self.gif_multiple_resize.setChecked(False)
            # Hide the variant controls
            self.gif_resize_variants.setVisible(False)
            self.gif_resize_variants_label.setVisible(False)
            # Note: No need to show single resize controls since "No resize" hides them anyway
        
        # Only show/hide resize input when not in "multiple variants" mode
        if hasattr(self, 'gif_multiple_resize') and self.gif_multiple_resize.isChecked():
            return
            
        if mode == "No resize":
            self.gif_resize_value.setVisible(False)
            self.gif_resize_value_label.setVisible(False)
        else:
            self.gif_resize_value.setVisible(True)
            self.gif_resize_value_label.setVisible(True)
            
            if mode == "By width (pixels)":
                self.gif_resize_value_label.setText("Width (pixels):")
                current_val = self.gif_resize_value.value()
                self.gif_resize_value.setRange(1, 10000)
                if current_val < 1 or current_val > 10000 or current_val == 33:
                    self.gif_resize_value.setValue(360)
            elif mode == "By longer edge (pixels)":
                self.gif_resize_value_label.setText("Longer edge (px):")
                current_val = self.gif_resize_value.value()
                self.gif_resize_value.setRange(1, 10000)
                if current_val < 1 or current_val > 10000 or current_val == 33:
                    self.gif_resize_value.setValue(360)
            elif mode == "By ratio (percent)":
                self.gif_resize_value_label.setText("Percentage:")
                # Check value BEFORE changing range (Qt clamps automatically)
                current_val = self.gif_resize_value.value()
                self.gif_resize_value.setRange(1, 200)
                if current_val < 1 or current_val > 200:
                    self.gif_resize_value.setValue(33)

    def on_image_size_mode_changed(self, mode):
        """Handle Image size mode change between Manual, Max Size, and Presets"""
        if mode not in ["Max Size", "Manual", "Presets", "Lab_presets"]:
            return
            
        is_max_size = (mode == "Max Size")
        is_manual = (mode == "Manual")
        is_presets = (mode == "Presets" or mode == "Lab_presets")
        
        # Override visibility if Lab inactive (hide manual controls)
        if hasattr(self, 'lab_btn') and not self.lab_btn.is_solid and not is_presets:
             is_max_size = False
             is_manual = False
        
        # Normalize internal value
        if is_presets:
            self.image_size_mode_value = "presets"
        else:
            self.image_size_mode_value = mode.lower().replace(" ", "_")
        
        # Max Size visibility
        self.image_max_size_label.setVisible(is_max_size)
        self.image_max_size_spinbox.setVisible(is_max_size)
        self.image_auto_resize_checkbox.setVisible(is_max_size)
        
        # Quality visibility
        self.multiple_qualities.setVisible(is_manual)
        variants_enabled = self.multiple_qualities.isChecked() if is_manual else False
        self.image_quality.setVisible(is_manual and not variants_enabled)
        self.image_quality_label.setVisible(is_manual and not variants_enabled)
        self.image_quality_row_label.setVisible(is_manual and not variants_enabled)
        self.quality_variants.setVisible(is_manual and variants_enabled)
        self.quality_variants_label.setVisible(is_manual and variants_enabled)
        
        # Presets visibility
        self.image_presets_section.setVisible(is_presets)
        
        # Format visibility - hide in presets mode
        self.image_format.setVisible(is_manual or is_max_size)
        
        # Transformation adjustments
        if is_presets:
            self.image_resize_mode.setCurrentText("No resize")
        
        self.image_transform_group.setVisible(is_manual or is_max_size)

    def on_video_size_mode_changed(self, mode):
        """Handle Video size mode change between Manual, Max Size, and Presets"""
        if mode not in ["Max Size", "Manual", "Presets", "Lab_presets"]:
            return
            
        is_max_size = (mode == "Max Size")
        is_manual = (mode == "Manual")
        is_presets = (mode == "Presets" or mode == "Lab_presets")
        
        # Override visibility if Lab inactive (hide manual controls)
        if hasattr(self, 'lab_btn') and not self.lab_btn.is_solid and not is_presets:
             is_max_size = False
             is_manual = False
        
        # Normalize internal value
        if is_presets:
            self.video_size_mode_value = "presets"
        else:
            self.video_size_mode_value = mode.lower().replace(" ", "_")
        
        # Max Size visibility
        self.video_max_size_label.setVisible(is_max_size)
        self.video_max_size_spinbox.setVisible(is_max_size)
        self.video_auto_resize_checkbox.setVisible(is_max_size)
        
        # Quality visibility
        self.multiple_video_qualities.setVisible(is_manual)
        variants_enabled = self.multiple_video_qualities.isChecked() if is_manual else False
        self.video_quality.setVisible(is_manual and not variants_enabled)
        self.video_quality_label.setVisible(is_manual and not variants_enabled)
        self.video_quality_value.setVisible(is_manual and not variants_enabled)
        self.video_quality_variants.setVisible(is_manual and variants_enabled)
        self.video_quality_variants_label.setVisible(is_manual and variants_enabled)
        
        # Presets visibility
        self.video_presets_section.setVisible(is_presets)
        
        # Format visibility - hide in presets mode
        self.video_codec.setVisible(is_manual or is_max_size)
        
        # Transformation adjustments
        if is_presets:
            self.video_resize_mode.setCurrentText("No resize")

        self.video_transform_group.setVisible(is_manual or is_max_size)

    def on_loop_size_mode_changed(self, mode):
        """Handle Loop size mode change (GIF/WebM)"""
        if mode not in ["Max Size", "Manual", "Presets", "Lab_presets"]:
            return
            
        is_max_size = (mode == "Max Size")
        is_manual = (mode == "Manual")
        is_presets = (mode == "Presets" or mode == "Lab_presets")
        
        # Override visibility if Lab inactive (hide manual controls)
        if hasattr(self, 'lab_btn') and not self.lab_btn.is_solid and not is_presets:
             is_max_size = False
             is_manual = False
        
        # Normalize internal value
        if is_presets:
            self.loop_size_mode_value = "presets"
        else:
            self.loop_size_mode_value = mode.lower().replace(" ", "_")
        
        # Determine format for manual visibility
        format_name = self.loop_format.currentText()
        is_gif = (format_name == "GIF")
        
        # State updates
        self.gif_max_size_label.setVisible(is_max_size)
        self.gif_max_size_spinbox.setVisible(is_max_size)
        self.gif_auto_resize_checkbox.setVisible(is_max_size)
        
        # Manual settings visibility
        # Determine variant states
        gif_variants_enabled = self.gif_ffmpeg_variants.isChecked() if (is_manual and is_gif and hasattr(self, 'gif_ffmpeg_variants')) else False
        webm_variants_enabled = self.loop_webm_variants.isChecked() if (is_manual and not is_gif and hasattr(self, 'loop_webm_variants')) else False
        
        # Show GIF widgets (hide single-value when variants enabled)
        show_gif = is_manual and is_gif
        show_gif_single = show_gif and not gif_variants_enabled
        show_gif_variants = show_gif and gif_variants_enabled
        
        # Show WebM widgets (hide single-value when variants enabled)
        show_webm = is_manual and not is_gif
        show_webm_single = show_webm and not webm_variants_enabled
        show_webm_variants = show_webm and webm_variants_enabled
        
        # GIF Multi-variant toggle (always visible in GIF manual mode)
        if hasattr(self, 'gif_ffmpeg_variants'):
             self.gif_ffmpeg_variants.setVisible(show_gif)
        
        # GIF Single-value widgets (hidden when variants enabled)
        if hasattr(self, 'ffmpeg_gif_fps_label'):
             self.ffmpeg_gif_fps_label.setVisible(show_gif_single)
             self.ffmpeg_gif_fps.setVisible(show_gif_single)
        if hasattr(self, 'ffmpeg_gif_colors_label'):
             self.ffmpeg_gif_colors_label.setVisible(show_gif_single)
             self.ffmpeg_gif_colors.setVisible(show_gif_single)
        if hasattr(self, 'gif_dither_quality_slider'):
             self.gif_dither_quality_slider.setVisible(show_gif_single)
             self.gif_dither_quality_row_label.setVisible(show_gif_single)
        if hasattr(self, 'gif_dither_quality_label'):
             self.gif_dither_quality_label.setVisible(show_gif_single)
        if hasattr(self, 'ffmpeg_gif_blur'):
             self.ffmpeg_gif_blur.setVisible(show_gif)
             
        # GIF Variant inputs
        self.ffmpeg_gif_fps_variants_label.setVisible(show_gif_variants)
        self.ffmpeg_gif_fps_variants.setVisible(show_gif_variants)
        self.ffmpeg_gif_colors_variants_label.setVisible(show_gif_variants)
        self.ffmpeg_gif_colors_variants.setVisible(show_gif_variants)
        self.ffmpeg_gif_dither_variants_label.setVisible(show_gif_variants)
        self.ffmpeg_gif_dither_variants.setVisible(show_gif_variants)
             
        # WebM Multi-variant toggle (always visible in WebM manual mode)
        if hasattr(self, 'loop_webm_variants'):
             self.loop_webm_variants.setVisible(show_webm)
        
        # WebM Single-value widgets (hidden when variants enabled)
        if hasattr(self, 'loop_webm_quality'):
             self.loop_webm_quality.setVisible(show_webm_single)
             self.loop_webm_quality_value.setVisible(show_webm_single)
             self.loop_webm_quality_row_label.setVisible(show_webm_single)
        
        # WebM Variant inputs
        if hasattr(self, 'loop_webm_quality_variants'):
             self.loop_webm_quality_variants.setVisible(show_webm_variants)
             self.loop_webm_quality_variants_label.setVisible(show_webm_variants)
        
        # Presets visibility
        self.gif_presets_section.setVisible(is_presets)
        
        # Format visibility - hide in presets mode
        self.loop_format.setVisible(is_manual or is_max_size)
        
        # Transformation adjustments
        if is_presets:
            self.gif_resize_mode.setCurrentText("No resize")

        self.gif_transform_group.setVisible(is_manual or is_max_size)

    def toggle_video_variant_mode(self, checked):
        """Toggle between single and multiple video size variant modes"""
        # Show/hide video variant controls
        self.video_size_variants.setVisible(checked)
        self.video_size_variants_label.setVisible(checked)
        
        # Auto-select "By longer edge" if currently "No resize" when enabling variants
        if checked and self.video_resize_mode.currentText() == "No resize":
            self.video_resize_mode.setCurrentText("By longer edge (pixels)")
        
        # Hide single resize controls when using variants
        if checked:
            self.video_resize_value.setVisible(False)
            self.video_resize_value_label.setVisible(False)
            # Update placeholder and default values based on current mode
            current_mode = self.video_resize_mode.currentText()
            if current_mode == "By ratio (percent)":
                self.video_size_variants.setPlaceholderText("e.g., 33,66,90")
                self.video_size_variants.setText("33,66")
            else:
                self.video_size_variants.setPlaceholderText("e.g., 480,720,960")
                self.video_size_variants.setText("480,720,960")
        else:
            # Show single resize controls based on current mode
            current_mode = self.video_resize_mode.currentText()
            if current_mode != "No resize":
                self.video_resize_value.setVisible(True)
                self.video_resize_value_label.setVisible(True)
                # Configure the control based on current mode
                if current_mode == "By width (pixels)":
                    self.video_resize_value_label.setText("Width (pixels):")
                    self.video_resize_value.setRange(1, 10000)
                    # Set a reasonable default if current value is out of range
                    current_val = self.video_resize_value.value()
                    if current_val < 1 or current_val > 10000:
                        self.video_resize_value.setValue(640)
                elif current_mode == "By ratio (percent)":
                    self.video_resize_value_label.setText("Percentage:")
                    self.video_resize_value.setRange(1, 200)
                    # Set a reasonable default if current_val is out of range
                    current_val = self.video_resize_value.value()
                    if current_val < 1 or current_val > 200:
                        self.video_resize_value.setValue(50)
                
    def get_video_resize_values(self):
        """Get list of video resize values from input with size validation"""
        # Check if multiple resize variants are enabled
        if hasattr(self, 'multiple_video_variants') and self.multiple_video_variants.isChecked():
            resize_text = self.video_size_variants.text().strip()
            if not resize_text:
                return []
            
            # Get current mode to determine value format
            current_mode = self.video_resize_mode.currentText() if hasattr(self, 'video_resize_mode') else "By width (pixels)"
            
            sizes = []
            for value in resize_text.split(','):
                value = value.strip()
                if value:
                    try:
                        if value.endswith('%'):
                            percent = float(value[:-1])
                            if 1 <= percent <= 200:
                                sizes.append(f"{percent}%")
                        elif current_mode == "By longer edge (pixels)":
                            width = int(value)
                            if width > 0:
                                sizes.append(f"L{width}")
                        else:
                            width = int(value)
                            if width > 0:
                                sizes.append(str(width))
                    except (ValueError, TypeError):
                        continue
            return sizes
        else:
            # Single resize mode - check if resize is enabled
            if hasattr(self, 'video_resize_mode') and self.video_resize_mode.currentText() != "No resize":
                mode = self.video_resize_mode.currentText()
                value = self.video_resize_value.value()
                
                if mode == "By ratio (percent)":
                    return [f"{value}%"]
                elif mode == "By width (pixels)":
                    return [str(value)]
                elif mode == "By longer edge (pixels)":
                    return [f"L{value}"]
            
            return []
    
    def get_video_variant_values(self):
        """Get video size variant values"""
        if not (hasattr(self, 'multiple_video_variants') and self.multiple_video_variants.isChecked()):
            return []
        
        size_text = self.video_size_variants.text().strip()
        if not size_text:
            return []
        
        # Check current resize mode to determine how to interpret values
        current_mode = self.video_resize_mode.currentText() if hasattr(self, 'video_resize_mode') else "By width (pixels)"
        
        sizes = []
        for value in size_text.split(','):
            value = value.strip()
            if value:
                try:
                    if value.endswith('%'):
                        percent = float(value[:-1])
                        if 1 <= percent <= 200:
                            sizes.append(f"{percent}%")
                    else:
                        # If mode is "By ratio (percent)", treat numeric values as percentages
                        if current_mode == "By ratio (percent)":
                            percent = float(value)
                            if 1 <= percent <= 200:
                                sizes.append(f"{percent}%")
                        else:
                            # Mode is "By width (pixels)", treat as pixel width
                            width = int(value)
                            if width > 0:
                                sizes.append(str(width))
                except (ValueError, TypeError):
                    continue
        
        return sizes

    
    def toggle_video_quality_mode(self, checked):
        """Toggle between single and multiple video quality variant modes"""
        # Show/hide video quality variant controls
        self.video_quality_variants.setVisible(checked)
        self.video_quality_variants_label.setVisible(checked)
        
        # Hide single quality controls when using variants
        if checked:
            self.video_quality.setVisible(False)
            self.video_quality_label.setVisible(False)
            self.video_quality_value.setVisible(False)
        else:
            # Show single quality controls
            self.video_quality.setVisible(True)
            self.video_quality_label.setVisible(True)
            self.video_quality_value.setVisible(True)
    
    def toggle_time_cutting(self, checked):
        """Toggle time cutting controls visibility"""
        try:
            if hasattr(self, 'time_range_slider'):
                self.time_range_slider.setVisible(checked)
        except Exception as e:
            print(f"Error toggling time cutting: {e}")

    def toggle_retime(self, checked):
        """Toggle retime slider visibility"""
        try:
            if hasattr(self, 'retime_slider'):
                self.retime_slider.setVisible(checked)
            if hasattr(self, 'retime_value_label'):
                self.retime_value_label.setVisible(checked)
        except Exception as e:
            print(f"Error toggling retime: {e}")
    
    def toggle_gif_time_cutting(self, checked):
        """Toggle GIF time cutting controls visibility"""
        try:
            if hasattr(self, 'gif_time_range_slider'):
                self.gif_time_range_slider.setVisible(checked)
        except Exception as e:
            print(f"Error toggling GIF time cutting: {e}")

    def toggle_gif_retime(self, checked):
        """Toggle GIF retime slider visibility"""
        try:
            if hasattr(self, 'gif_retime_slider'):
                self.gif_retime_slider.setVisible(checked)
            if hasattr(self, 'gif_retime_value_label'):
                self.gif_retime_value_label.setVisible(checked)
        except Exception as e:
            print(f"Error toggling GIF retime: {e}")
    
    def on_video_codec_changed(self, codec):
        """Handle video codec change - refresh visibility based on current mode"""
        # Only refresh if video tab is fully initialized
        if not hasattr(self, 'video_transform_group'):
            return
        # Re-apply size mode visibility to respect current mode and multi-variant state
        current_mode = getattr(self, 'video_size_mode_value', 'max_size').replace('_', ' ').title()
        self.on_video_size_mode_changed(current_mode)
        # Update GPU indicator
        self._update_gpu_indicator()

    
    def get_quality_values(self):
        """Get list of quality values from input"""
        if hasattr(self, 'multiple_qualities') and self.multiple_qualities.isChecked():
            quality_text = self.quality_variants.text().strip()
            if not quality_text:
                return [75]  # Default quality
            
            try:
                qualities = [int(q.strip()) for q in quality_text.split(',') if q.strip()]
                # Validate quality values (1-100)
                qualities = [max(1, min(100, q)) for q in qualities]
                return qualities if qualities else [75]
            except ValueError:
                return [75]  # Default on error
        else:
            # Single quality mode
            if hasattr(self, 'image_quality'):
                return [self.image_quality.value()]
            return [75]


    
    def toggle_gifsicle_variant_mode(self, enabled):
        """Toggle Gifsicle optimization variant inputs"""
        # Show/hide variant inputs
        self.gif_fps_variants.setVisible(enabled)
        self.gif_fps_variants_label.setVisible(enabled)
        self.gif_optimization_variants.setVisible(enabled)
        self.gif_optimization_variants_label.setVisible(enabled)
        self.gif_colors_variants.setVisible(enabled)
        self.gif_colors_variants_label.setVisible(enabled)
        self.gif_lossy_variants.setVisible(enabled)
        self.gif_lossy_variants_label.setVisible(enabled)
        
        # Hide/show single inputs and their labels (opposite of variants)
        self.gif_fps.setVisible(not enabled)
        self.gif_fps_single_label.setVisible(not enabled)
        self.gif_optimization.setVisible(not enabled)
        self.gif_optimization_single_label.setVisible(not enabled)
        self.gif_colors.setVisible(not enabled)
        self.gif_colors_single_label.setVisible(not enabled)
        self.gif_lossy.setVisible(not enabled)
        self.gif_lossy_single_label.setVisible(not enabled)
    
    def on_gif_resize_mode_changed(self, mode):
        """Handle GIF resize mode change to update default values and labels"""
        # Uncheck multi-variant toggle if switching to "No resize"
        if mode == "No resize" and hasattr(self, 'gif_multiple_resize') and self.gif_multiple_resize.isChecked():
            self.gif_multiple_resize.blockSignals(True)
            self.gif_multiple_resize.setChecked(False)
            self.gif_multiple_resize.blockSignals(False)
            # Manually trigger the toggle handler to update UI
            self.toggle_gif_resize_variant_mode(False)
        
        # Check if multiple variants mode is active - if so, don't show single controls
        multiple_enabled = hasattr(self, 'gif_multiple_resize') and self.gif_multiple_resize.isChecked()
        
        if mode == "No resize" or multiple_enabled:
            self.gif_resize_value.setVisible(False)
            self.gif_resize_value_label.setVisible(False)
        elif mode == "By ratio (percent)":
            self.gif_resize_value.setVisible(True)
            self.gif_resize_value_label.setVisible(True)
            self.gif_resize_value_label.setText("Percentage:")
            current_val = self.gif_resize_value.value()
            self.gif_resize_value.setRange(1, 200)
            if current_val < 1 or current_val > 200:
                self.gif_resize_value.setValue(33)  # Default 33%
            self.gif_resize_value.setSuffix("")
        elif mode == "By width (pixels)":
            self.gif_resize_value.setVisible(True)
            self.gif_resize_value_label.setVisible(True)
            self.gif_resize_value_label.setText("Width (pixels):")
            current_val = self.gif_resize_value.value()
            self.gif_resize_value.setRange(1, 10000)
            if current_val < 1 or current_val > 10000 or current_val == 33:
                self.gif_resize_value.setValue(360)  # Default 360px
            self.gif_resize_value.setSuffix("")
            
        # Update variants if multiple mode is enabled
        if multiple_enabled:
            if mode == "By ratio (percent)":
                self.gif_resize_variants.setPlaceholderText("e.g., 33,66,90")
                self.gif_resize_variants.setText("33,66")
            else:
                self.gif_resize_variants.setPlaceholderText("e.g., 240,360,480")
                self.gif_resize_variants.setText("240,360,480")
                
    def toggle_gif_resize_variant_mode(self, checked):
        """Toggle between single and multiple GIF resize variant modes"""
        # Show/hide resize variant controls
        self.gif_resize_variants.setVisible(checked)
        self.gif_resize_variants_label.setVisible(checked)
        
        # Auto-select "By longer edge" if currently "No resize" when enabling variants
        if checked and self.gif_resize_mode.currentText() == "No resize":
            self.gif_resize_mode.setCurrentText("By longer edge (pixels)")
        
        # Hide single resize controls when using variants
        if checked:
            self.gif_resize_value.setVisible(False)
            self.gif_resize_value_label.setVisible(False)
            # Update placeholder and default values based on current mode
            current_mode = self.gif_resize_mode.currentText()
            if current_mode == "By width (pixels)" or current_mode == "By longer edge (pixels)":
                self.gif_resize_variants.setPlaceholderText("e.g., 240,360,480")
                self.gif_resize_variants.setText("240,360,480")
            else:
                self.gif_resize_variants.setPlaceholderText("e.g., 33,66,90")
                self.gif_resize_variants.setText("33,66")
        else:
            # Show single resize controls based on current mode
            current_mode = self.gif_resize_mode.currentText()
            if current_mode != "No resize":
                self.gif_resize_value.setVisible(True)
                self.gif_resize_value_label.setVisible(True)
                # Configure the control based on current mode
                if current_mode == "By width (pixels)":
                    self.gif_resize_value_label.setText("Width (pixels):")
                    self.gif_resize_value.setRange(1, 10000)
                    # Set a reasonable default if current value is out of range
                    current_val = self.gif_resize_value.value()
                    if current_val < 1 or current_val > 10000:
                        self.gif_resize_value.setValue(720)
                elif current_mode == "By ratio (percent)":
                    self.gif_resize_value_label.setText("Percentage:")
                    self.gif_resize_value.setRange(1, 200)
                    # Set a reasonable default if current value is out of range
                    current_val = self.gif_resize_value.value()
                    if current_val < 1 or current_val > 200:
                        self.gif_resize_value.setValue(50)
                
    def get_gif_resize_values(self):
        """Get list of GIF resize values from input with size validation"""
        # Check if multiple resize variants are enabled
        if hasattr(self, 'gif_multiple_resize') and self.gif_multiple_resize.isChecked():
            resize_text = self.gif_resize_variants.text().strip()
            if not resize_text:
                return []
            
            # Check current resize mode to determine how to interpret values
            current_mode = self.gif_resize_mode.currentText() if hasattr(self, 'gif_resize_mode') else "By width (pixels)"
            
            sizes = []
            for value in resize_text.split(','):
                value = value.strip()
                if value:
                    try:
                        if value.endswith('%'):
                            percent = float(value[:-1])
                            if 1 <= percent <= 200:
                                sizes.append(f"{percent}%")
                        else:
                            # If mode is "By ratio (percent)", treat numeric values as percentages
                            if current_mode == "By ratio (percent)":
                                percent = float(value)
                                if 1 <= percent <= 200:
                                    sizes.append(f"{percent}%")
                            elif current_mode == "By longer edge (pixels)":
                                # Mode is "By longer edge (pixels)", prefix with "L"
                                width = int(value)
                                if width > 0:
                                    sizes.append(f"L{width}")
                            else:
                                # Mode is "By width (pixels)", treat as pixel width
                                width = int(value)
                                if width > 0:
                                    sizes.append(str(width))
                    except (ValueError, TypeError):
                        continue
            return sizes
        else:
            # Single resize mode - check if resize is enabled
            if hasattr(self, 'gif_resize_mode') and self.gif_resize_mode.currentText() != "No resize":
                mode = self.gif_resize_mode.currentText()
                value = self.gif_resize_value.value()
                
                if mode == "By ratio (percent)":
                    return [f"{value}%"]
                elif mode == "By width (pixels)":
                    # Add size validation here if needed
                    return [str(value)]
                elif mode == "By longer edge (pixels)":
                    return [f"L{value}"]
            
            return []
    

    def validate_fps_variants(self):
        """Validate FPS variants input range (1-240)"""
        text = self.gif_fps_variants.text().strip()
        if not text:
            return
            
        try:
            values = [int(val.strip()) for val in text.split(',') if val.strip()]
            invalid_values = [val for val in values if val < 1 or val > 240]
            
            if invalid_values:
                from PySide6.QtWidgets import QMessageBox
                msg_box = QMessageBox(QMessageBox.Icon.Warning, "Invalid FPS Values", 
                                    f"FPS values must be between 1 and 240.\n\nInvalid values found: {invalid_values}\n\nValid range: 1 to 240\n\nCommon FPS values:\n10-15 = Low motion\n24-30 = Standard motion\n60+ = High motion", 
                                    parent=self)
                # Apply dark mode styling - get parent window's theme manager
                try:
                    main_window = self
                    while main_window.parent():
                        main_window = main_window.parent()
                    if hasattr(main_window, 'theme_manager'):
                        msg_box.setStyleSheet(main_window.theme_manager.get_dialog_styles())
                except:
                    pass
                msg_box.exec()
                # Reset to valid default
                self.gif_fps_variants.setText("10,15,30")
        except ValueError:
            # Ignore non-numeric input during typing
            pass
            
    def validate_colors_variants(self):
        """Validate Colors variants input range (2-256)"""
        text = self.gif_colors_variants.text().strip()
        if not text:
            return
            
        try:
            values = [int(val.strip()) for val in text.split(',') if val.strip()]
            invalid_values = [val for val in values if val < 2 or val > 256]
            
            if invalid_values:
                from PySide6.QtWidgets import QMessageBox
                msg_box = QMessageBox(QMessageBox.Icon.Warning, "Invalid Colors Values", 
                                    f"Colors values must be between 2 and 256.\n\nInvalid values found: {invalid_values}\n\nValid range: 2 to 256\n\nColor recommendations:\n2-16 = Very low quality\n32-64 = Low quality\n128-256 = High quality", 
                                    parent=self)
                # Apply dark mode styling - get parent window's theme manager
                try:
                    main_window = self
                    while main_window.parent():
                        main_window = main_window.parent()
                    if hasattr(main_window, 'theme_manager'):
                        msg_box.setStyleSheet(main_window.theme_manager.get_dialog_styles())
                except:
                    pass
                msg_box.exec()
                # Reset to valid default
                self.gif_colors_variants.setText("64,128,256")
        except ValueError:
            # Ignore non-numeric input during typing
            pass
            


    def validate_video_quality_variants(self):
        """Validate video quality variants input range (0-100)"""
        text = self.video_quality_variants.text().strip()
        if not text:
            return
            
        try:
            values = [int(val.strip()) for val in text.split(',') if val.strip()]
            invalid_values = [val for val in values if val < 0 or val > 100]
            
            if invalid_values:
                from PySide6.QtWidgets import QMessageBox
                msg_box = QMessageBox(QMessageBox.Icon.Warning, "Invalid Quality Values", 
                                    f"Quality values must be between 0 and 100.\n\nInvalid values found: {invalid_values}\n\nValid range: 0 to 100\n\nQuality levels:\n0 = Lossless\n25-40 = High quality\n50-70 = Good quality (recommended)\n80-100 = Low quality", 
                                    parent=self)
                # Apply dark mode styling - get parent window's theme manager
                try:
                    main_window = self
                    while main_window.parent():
                        main_window = main_window.parent()
                    if hasattr(main_window, 'theme_manager'):
                        msg_box.setStyleSheet(main_window.theme_manager.get_dialog_styles())
                except:
                    pass
                msg_box.exec()
                # Reset to valid default
                self.video_quality_variants.setText("15,23,31")
        except ValueError:
            # Ignore non-numeric input during typing
            pass










