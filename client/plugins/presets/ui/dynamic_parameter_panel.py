from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QApplication, QPushButton, QScrollArea, QWidget
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Signal, QTimer, Property, Qt
from PySide6.QtGui import QPixmap, QPainter, QIcon
from PySide6.QtSvg import QSvgRenderer
from typing import Optional
from client.gui.animators.animation_driver import AnimationDriver

# Maximum widget size in Qt
QWIDGETSIZE_MAX = 16777215

class DynamicParameterPanel(QFrame):
    """
    Self-contained parameter panel with adaptive sizing and smooth animations.
    
    Features:
    - Accurate height calculation based on actual content after layout settles
    - Smooth grow/shrink animations with proper easing using fixedHeight
    - Automatic re-animation when content visibility changes
    - Proper padding and spacing between parameters
    - AnimationDriver integration for dev panel tuning
    """
    
    go_to_lab_clicked = Signal(dict)  # Emits lab_mode_settings
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DynamicParamPanel")
        
        # Animation configuration (tunable via dev panel)
        # These are instance attributes so dev_panel can modify them
        self.ANIM_DURATION = 330  # ms - slightly longer for smoother feel
        self.EASING_CURVE = 'InQuart'  # Snappy start, gentle end for opening
        self.CLOSE_EASING = 'InQuad'  # Smooth acceleration for closing
        
        # Layout constants
        self.PANEL_PADDING_H = 24  # Horizontal padding
        self.PANEL_PADDING_TOP = 16
        self.PANEL_PADDING_BOTTOM = 24
        self.TITLE_SPACING = 12  # Space below title
        
        # Height calculation
        self.MIN_PANEL_HEIGHT = 80  # Minimum visible height
        self.HEIGHT_BUFFER = 8  # Small buffer for rounding errors
        self.LAYOUT_SETTLE_DELAY = 23  # ms to wait for Qt layout to settle
        self.MAX_FORM_HEIGHT_RATIO = 0.75  # Form scroll area capped at 75% of gallery height

        
        # Animation state
        self._anim: Optional[QPropertyAnimation] = None
        self._last_height = 0  # Track last stable height for smooth transitions
        self._current_animated_height = 0  # Track current height during animation
        self._is_animating = False
        self._is_minimized = False
        self._pending_height_update = False
        
        # Layout with proper padding
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            self.PANEL_PADDING_H, 
            self.PANEL_PADDING_TOP, 
            self.PANEL_PADDING_H, 
            self.PANEL_PADDING_BOTTOM
        )
        self._layout.setSpacing(self.TITLE_SPACING)
        
        # Title label
        self._title_label = QLabel()
        self._title_label.setObjectName("ParamPanelTitle")
        self._update_title_style()
        self._layout.addWidget(self._title_label)
        
        # Description label (always visible, below title)
        self._description_label = QLabel()
        self._description_label.setObjectName("ParamPanelDescription")
        self._description_label.setWordWrap(True)
        self._update_description_style()
        self._layout.addWidget(self._description_label)
        
        # Go to Lab button (hidden by default, shown for Lab Mode reference presets)
        # Custom button with lab vial icons on both sides
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import QSize
        
        # Create a container widget for the button
        self._go_to_lab_btn = QPushButton()
        self._go_to_lab_btn.setObjectName("GoToLabButton")
        self._go_to_lab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._go_to_lab_btn.hide()
        
        # Create a horizontal layout for the button content
        btn_layout = QHBoxLayout(self._go_to_lab_btn)
        btn_layout.setContentsMargins(16, 8, 16, 8)
        btn_layout.setSpacing(12)
        
        # Left vial icon
        self._left_vial_icon = QLabel()
        self._left_vial_icon.setFixedSize(28, 28)
        self._left_vial_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(self._left_vial_icon)
        
        # Text label
        self._btn_text_label = QLabel("Go to Lab Settings")
        self._btn_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._btn_text_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                color: white;
                font-size: 16px;
                font-weight: 600;
            }
        """)
        btn_layout.addWidget(self._btn_text_label, 1)
        
        # Right vial icon
        self._right_vial_icon = QLabel()
        self._right_vial_icon.setFixedSize(28, 28)
        self._right_vial_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(self._right_vial_icon)
        
        self._layout.addWidget(self._go_to_lab_btn)
        
        # Scroll area wrapping the parameter form
        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("ParamScrollArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.hide()  # Hidden until a form is loaded
        self._layout.addWidget(self._scroll_area)
        
        # Parameter form container (set via set_content)
        self._parameter_form = None

        
        # Initially hidden
        self.hide()
        self.setFixedHeight(0)
        
        self._apply_styles()
        self._update_go_to_lab_button_style()
    
    # Custom property for smooth height animation - uses setFixedHeight to bypass layout constraints
    @Property(int)
    def animatedHeight(self):
        """Get current animated height."""
        return self._current_animated_height
    
    @animatedHeight.setter
    def animatedHeight(self, h):
        """Set height using setFixedHeight for smooth shrink animations."""
        self._current_animated_height = h
        self.setFixedHeight(h)
    
    def _apply_styles(self):
        """Apply panel styling."""
        from client.gui.theme_variables import get_color
        from client.gui.theme_manager import ThemeManager
        
        is_dark = ThemeManager.instance().is_dark_mode()
        panel_bg = get_color("gallery_param_panel_bg", is_dark)
        scrollbar_bg = get_color("gallery_param_panel_bg", is_dark)
        
        from client.gui.theme import Theme
        
        self.setStyleSheet(f"""
            QFrame#DynamicParamPanel {{
                background: {panel_bg};
                border-radius: 8px;
            }}
            QScrollArea#ParamScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea#ParamScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {Theme.color('scrollbar_bg')};
                width: 8px;
                border: none;
                border-radius: 4px;
                margin: 4px 2px 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.color('scrollbar_thumb')};
                border-radius: 4px;
                min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Theme.border_focus()};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
    
    def _update_go_to_lab_button_style(self):
        """Update Go to Lab button styling."""
        from client.gui.theme_variables import get_color
        from client.gui.theme_manager import ThemeManager
        
        is_dark = ThemeManager.instance().is_dark_mode()
        # Use existing btn_lab_solid color (blue) - accent_secondary doesn't exist
        accent = get_color("btn_lab_solid", is_dark)
        accent_hover = get_color("info", is_dark)  # Use info blue for hover
        
        self._go_to_lab_btn.setStyleSheet(f"""
            QPushButton#GoToLabButton {{
                background-color: {accent};
                border: none;
                border-radius: 6px;
                min-width: 240px;
                min-height: 52px;
            }}
            QPushButton#GoToLabButton:hover {{
                background-color: {accent_hover};
            }}
            QPushButton#GoToLabButton:pressed {{
                background-color: {accent};
            }}
        """)
        
        # Load vial icons
        self._load_vial_icons()
    
    def _load_vial_icons(self):
        """Load lab vial icons for the button."""
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray, QRectF
        from client.utils.resource_path import get_resource_path
        import re
        
        # Get the lab vial icon path
        vial_icon_path = get_resource_path('client/assets/icons/lab_icon.svg')
        
        try:
            with open(vial_icon_path, 'r', encoding='utf-8') as f:
                vial_svg = f.read()
            
            # Apply white color to SVG for visibility on blue background
            vial_svg = re.sub(r'fill="(?!none)[^"]*"', f'fill="white"', vial_svg)
            vial_svg = re.sub(r'stroke="(?!none)[^"]*"', f'stroke="white"', vial_svg)
            
            # Render to pixmap
            renderer = QSvgRenderer(QByteArray(vial_svg.encode('utf-8')))
            pixmap = QPixmap(28, 28)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            renderer.render(painter)
            painter.end()
            
            # Set the same icon for both left and right
            self._left_vial_icon.setPixmap(pixmap)
            self._right_vial_icon.setPixmap(pixmap)
        except Exception as e:
            print(f"[DynamicParameterPanel] Error loading vial icons: {e}")
    

    
    def _update_title_style(self):
        """Update title label styling."""
        from client.gui.theme_variables import get_color
        from client.gui.theme_manager import ThemeManager
        
        is_dark = ThemeManager.instance().is_dark_mode()
        text_color = get_color("text_primary", is_dark)
        
        self._title_label.setStyleSheet(f"""
            QLabel#ParamPanelTitle {{
                font-size: 16px;
                font-weight: bold;
                color: {text_color};
            }}
        """)
    
    def _update_description_style(self):
        """Update description label styling."""
        from client.gui.theme_variables import get_color
        from client.gui.theme_manager import ThemeManager
        
        is_dark = ThemeManager.instance().is_dark_mode()
        text_muted = get_color("text_secondary", is_dark)
        
        self._description_label.setStyleSheet(f"""
            QLabel#ParamPanelDescription {{
                font-size: 13px;
                color: {text_muted};
                margin-top: 4px;
                margin-bottom: 8px;
            }}
        """)
    
    def update_theme(self, is_dark: bool):
        """Update theme when dark/light mode changes."""
        self._apply_styles()
        self._update_title_style()
        self._update_description_style()
        self._update_go_to_lab_button_style()
        if self._parameter_form and hasattr(self._parameter_form, 'update_theme'):
            self._parameter_form.update_theme(is_dark)
    
    def set_content(self, title: str, parameter_form, description: str = "", preset=None):
        """
        Set the panel content.
        
        Args:
            title: Title text to display
            parameter_form: ParameterForm widget to display (can be None)
            description: Description text to display below title
            preset: PresetDefinition object (optional, for Lab Mode detection)
        """
        # Reset minimized state when content changes significantly (like selecting a new card)
        if getattr(self, '_is_minimized', False):
            self._is_minimized = False
            
        self._title_label.setText(title)
        
        # Always show description (or default message if empty)
        if description:
            self._description_label.setText(description)
        else:
            self._description_label.setText("No parameters required for this preset.")
        
        # Show/hide Go to Lab button based on preset type
        if preset and preset.raw_yaml.get('meta', {}).get('execution_mode') == 'lab_mode_reference':
            lab_settings = preset.raw_yaml.get('lab_mode_settings', {})
            if lab_settings:
                self._go_to_lab_btn.show()
                # Disconnect any previous connections
                try:
                    self._go_to_lab_btn.clicked.disconnect()
                except:
                    pass
                # Connect button click to emit lab settings
                self._go_to_lab_btn.clicked.connect(
                    lambda: self.go_to_lab_clicked.emit(lab_settings)
                )
            else:
                self._go_to_lab_btn.hide()
        else:
            self._go_to_lab_btn.hide()
        
        # Remove old parameter form if exists
        if self._parameter_form and self._parameter_form != parameter_form:
            # Disconnect old signals
            try:
                self._parameter_form.values_changed.disconnect(self._on_content_changed)
            except:
                pass
            self._scroll_area.takeWidget() # Remove widget from scroll area
        
        # Add new parameter form if provided and not already added
        if parameter_form and self._parameter_form != parameter_form:
            self._parameter_form = parameter_form
            # Prevent form from stretching to fill scroll viewport (would defeat scrolling)
            from PySide6.QtWidgets import QSizePolicy
            parameter_form.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            self._scroll_area.setWidget(self._parameter_form)
            self._scroll_area.show()
            # Connect to values_changed to detect visibility changes
            self._parameter_form.values_changed.connect(self._on_content_changed)
        elif not parameter_form:
            # No parameters - just show title and description
            self._parameter_form = None
            self._scroll_area.hide()

        
        # Force layout update
        if self._parameter_form:
            self._parameter_form.updateGeometry()
        self.updateGeometry()
    
    def _on_content_changed(self, values: dict):
        """
        Handle content changes (e.g., visibility rules hiding/showing widgets).
        Re-animate to new height if panel is visible.
        """
        if self.isVisible():
            # Schedule height update with delay to let visibility changes settle
            # Allow even if animating - will smoothly transition to new height
            if not self._pending_height_update:
                self._pending_height_update = True
                QTimer.singleShot(self.LAYOUT_SETTLE_DELAY, self._update_height_animated)
    
    def _max_form_height(self) -> int:
        """Return max allowed height for the scroll area (75% of gallery/parent height)."""
        parent = self.parent()
        if parent:
            return int(parent.height() * self.MAX_FORM_HEIGHT_RATIO)
        return 400  # Sensible fallback

    def _calculate_content_height(self) -> int:
        """
        Calculate exact height needed for current content, capped so the panel
        never exceeds MAX_FORM_HEIGHT_RATIO of the parent (gallery) height.
        """
        # Process pending events to ensure layout is fully updated
        QApplication.processEvents()
        
        # Force layout recalculation
        self._layout.activate()
        if self._parameter_form and self._parameter_form.layout():
            self._parameter_form.layout().activate()
        
        # Get size hints
        title_hint = self._title_label.sizeHint()
        desc_hint = self._description_label.sizeHint()
        
        # Calculate fixed chrome height (margins + title + spacing + desc + button)
        chrome_height = 0
        chrome_height += self.PANEL_PADDING_TOP + self.PANEL_PADDING_BOTTOM
        chrome_height += max(title_hint.height(), 24)
        chrome_height += self.TITLE_SPACING
        chrome_height += max(desc_hint.height(), 20)
        
        if self._go_to_lab_btn.isVisible():
            chrome_height += self.TITLE_SPACING
            btn_hint = self._go_to_lab_btn.sizeHint()
            chrome_height += max(btn_hint.height(), 52)
        
        if self._parameter_form:
            chrome_height += 8  # Gap between desc and form
            
            form_hint = self._parameter_form.sizeHint()
            form_height = form_hint.height() if form_hint.height() > 0 else self._calculate_form_height_manual()
            
            # Cap form height at 75% of parent
            max_form = self._max_form_height()
            capped_form = min(form_height, max_form)
            self._scroll_area.setMaximumHeight(capped_form)
            
            chrome_height += capped_form
        
        return max(chrome_height + self.HEIGHT_BUFFER, self.MIN_PANEL_HEIGHT)

    
    def _calculate_form_height_manual(self) -> int:
        """
        Manually calculate form height by iterating visible widgets.
        Fallback when sizeHint doesn't work properly.
        """
        if not self._parameter_form:
            return 0
            
        form_layout = self._parameter_form.layout()
        if not form_layout:
            return 100
        
        height = 0
        visible_count = 0
        
        for i in range(form_layout.count()):
            item = form_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget and widget.isVisible():
                    # Get widget height
                    widget_height = widget.sizeHint().height()
                    if widget_height <= 0:
                        widget_height = widget.minimumSizeHint().height()
                    if widget_height <= 0:
                        widget_height = 50  # Fallback
                    
                    height += widget_height
                    visible_count += 1
        
        # Add spacing between widgets
        if visible_count > 1:
            height += form_layout.spacing() * (visible_count - 1)
        
        # Add form margins
        margins = form_layout.contentsMargins()
        height += margins.top() + margins.bottom()
        
        return height
    
    def _update_height_animated(self):
        """
        Animate to new height when content changes while visible.
        """
        self._pending_height_update = False
        
        if not self.isVisible():
            return
        
        target_height = self._calculate_content_height()
        
        # Get current height from animation state or actual height
        if self._is_animating:
            current_height = self._current_animated_height
        else:
            current_height = max(self.height(), self._last_height, 1)
        
        # Only animate if height actually changed significantly
        if abs(target_height - current_height) < 5:
            self._last_height = target_height
            return
        
        self._animate_to_height(current_height, target_height, is_opening=target_height > current_height)
    
    def show_animated(self):
        """Animate panel to show content with smooth easing."""
        # Determine start height based on current state
        if not self.isVisible():
            # Panel is hidden - start from 0
            self.setFixedHeight(0)
            self.show()
            start_height = 0
        else:
            # Panel is already visible - start from current position
            if self._is_animating:
                start_height = self._current_animated_height
            else:
                start_height = max(self.height(), self._last_height, 1)
        
        # Stop any running animation first
        self._stop_current_animation()
        
        # Use delay to let layout fully settle before calculating height
        def do_animate():
            # Force a full layout update
            QApplication.processEvents()
            self._layout.activate()
            
            target_height = self._calculate_content_height()
            self._animate_to_height(start_height, target_height, is_opening=True)
        
        # Adequate delay for Qt layout system to settle (uses instance attribute)
        QTimer.singleShot(self.LAYOUT_SETTLE_DELAY, do_animate)
    
    def _animate_to_height(self, start_height: int, target_height: int, is_opening: bool = True):
        """
        Animate from current height to target height using AnimationDriver.
        
        Uses custom animatedHeight property with setFixedHeight() to ensure
        both grow and shrink animations work smoothly (bypasses layout min size).
        
        Args:
            start_height: Starting height in pixels
            target_height: Target height in pixels  
            is_opening: True for opening animation, False for closing
        """
        self._stop_current_animation()
        self._is_animating = True
        self._current_animated_height = start_height
        
        # Set immediate height to start value for smooth transition
        self.setFixedHeight(start_height)
        
        # Create animation targeting our custom property (uses setFixedHeight internally)
        # Parent to self to prevent garbage collection
        self._anim = QPropertyAnimation(self, b"animatedHeight", self)
        
        # Read current settings from instance (dev panel modifies these)
        duration = self.ANIM_DURATION
        easing_name = self.EASING_CURVE if is_opening else self.CLOSE_EASING
        
        # Configure animation directly (bypass AnimationDriver for debugging)
        self._anim.setDuration(duration)
        self._anim.setStartValue(start_height)
        self._anim.setEndValue(target_height)
        
        # Apply easing curve
        curve_type = AnimationDriver.EASING_MAP.get(easing_name, QEasingCurve.Type.OutQuad)
        self._anim.setEasingCurve(QEasingCurve(curve_type))
        
        # Update state when animation finishes
        def on_finished():
            self._is_animating = False
            self._last_height = target_height
            self._current_animated_height = target_height
            # Keep fixed height - don't reset to flexible (this was causing jumps)
        
        self._anim.finished.connect(on_finished)
        self._anim.start()
    
    def _stop_current_animation(self):
        """Stop any currently running animation and disconnect signals."""
        if hasattr(self, '_anim') and self._anim:
            self._anim.stop()
            try:
                self._anim.finished.disconnect()
            except:
                pass
        self._is_animating = False
    
    def minimize_animated(self, minimize_height=44):
        """Animate panel to slide down, leaving only the top portion (title) visible."""
        if not self.isVisible():
            # If not visible, we can't minimize it properly, but let's just show it minimized
            self.setFixedHeight(minimize_height)
            self._last_height = minimize_height
            self._current_animated_height = minimize_height
            self._is_minimized = True
            self.show()
            return
            
        if getattr(self, '_is_minimized', False):
            # Already minimized
            return
            
        # Get current height for smooth transition BEFORE stopping animation
        if self._is_animating:
            current_height = self._current_animated_height
        else:
            current_height = max(self.height(), self._last_height, 1)
            
        # If we're already smaller or equal to the target height, no need to shrink
        if current_height <= minimize_height:
            self._is_minimized = True
            return
            
        # Stop any existing animation
        self._stop_current_animation()
        self._is_animating = True
        self._is_minimized = True
        self._current_animated_height = current_height
        
        # Set immediate height to start value
        self.setFixedHeight(current_height)
        
        # Create animation targeting our custom property
        self._anim = QPropertyAnimation(self, b"animatedHeight", self)
        
        close_duration = int(self.ANIM_DURATION * 0.8)
        easing_name = self.CLOSE_EASING
        
        self._anim.setDuration(close_duration)
        self._anim.setStartValue(current_height)
        self._anim.setEndValue(minimize_height)
        
        curve_type = AnimationDriver.EASING_MAP.get(easing_name, QEasingCurve.Type.InQuad)
        self._anim.setEasingCurve(QEasingCurve(curve_type))
        
        def on_finished():
            self._is_animating = False
            self._last_height = minimize_height
            self._current_animated_height = minimize_height
            # Do NOT hide(), it remains visible but short
            
        self._anim.finished.connect(on_finished)
        self._anim.start()
    
    def hide_animated(self):
        """Animate panel to hide with smooth easing."""
        if not self.isVisible():
            return
        
        # Get current height for smooth transition BEFORE stopping animation
        if self._is_animating:
            current_height = self._current_animated_height
        else:
            current_height = max(self.height(), self._last_height, 1)
        
        # Stop any existing animation
        self._stop_current_animation()
        self._is_animating = True
        self._current_animated_height = current_height
        
        # Set immediate height to start value
        self.setFixedHeight(current_height)
        
        # Create animation targeting our custom property
        # Parent to self to prevent garbage collection
        self._anim = QPropertyAnimation(self, b"animatedHeight", self)
        
        # Read current settings from instance (dev panel modifies these)
        close_duration = int(self.ANIM_DURATION * 0.8)  # Slightly faster close
        easing_name = self.CLOSE_EASING
        
        # Configure animation directly
        self._anim.setDuration(close_duration)
        self._anim.setStartValue(current_height)
        self._anim.setEndValue(0)
        
        # Apply easing curve
        curve_type = AnimationDriver.EASING_MAP.get(easing_name, QEasingCurve.Type.InQuad)
        self._anim.setEasingCurve(QEasingCurve(curve_type))
        
        # Hide and reset when animation finishes
        def on_finished():
            self._is_animating = False
            self._is_minimized = False
            self._last_height = 0
            self._current_animated_height = 0
            self.hide()
        
        self._anim.finished.connect(on_finished)
        self._anim.start()
