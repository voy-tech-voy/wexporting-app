from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer
from typing import Optional

class DynamicParameterPanel(QFrame):
    """
    Self-contained parameter panel with adaptive sizing and smooth animations.
    
    Features:
    - Accurate height calculation based on actual content
    - Smooth grow/shrink animations without resets
    - Adaptive spacing for different parameter types
    """
    
    # Animation configuration (tunable via dev panel)
    ANIM_DURATION = 200  # ms
    EASING_CURVE = "OutCubic"  # Easing curve name
    
    # Minimum heights for different widget types
    MIN_PARAM_HEIGHT = 50  # Minimum height per parameter widget
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DynamicParamPanel")
        
        # Animation
        self._animation: Optional[QPropertyAnimation] = None
        self._pending_show = False  # Track if we're waiting for layout
        
        # Layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 20)
        self._layout.setSpacing(16)
        
        # Title label
        self._title_label = QLabel()
        self._title_label.setObjectName("ParamPanelTitle")
        self._update_title_style()
        self._layout.addWidget(self._title_label)
        
        # Parameter form container (will be set via set_content)
        self._parameter_form = None
        
        # Initially hidden
        self.hide()
        self.setMaximumHeight(0)
        
        self._apply_styles()
    
    def _apply_styles(self):
        """Apply panel styling."""
        self.setStyleSheet("""
            QFrame#DynamicParamPanel {
                background: #2a2a2a;
                border-radius: 8px;
            }
        """)
    
    def _update_title_style(self):
        """Update title label styling."""
        self._title_label.setStyleSheet("""
            QLabel#ParamPanelTitle {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
            }
        """)
    
    def set_content(self, title: str, parameter_form):
        """
        Set the panel content.
        
        Args:
            title: Title text to display
            parameter_form: ParameterForm widget to display
        """
        self._title_label.setText(title)
        
        # Remove old parameter form if exists
        if self._parameter_form and self._parameter_form != parameter_form:
            self._layout.removeWidget(self._parameter_form)
        
        # Add new parameter form if not already added
        if self._parameter_form != parameter_form:
            self._parameter_form = parameter_form
            self._layout.addWidget(self._parameter_form)
        
        # Force layout update
        self._parameter_form.updateGeometry()
        self.updateGeometry()
    
    def _calculate_content_height(self) -> int:
        """
        Calculate exact height needed for current content.
        
        Returns:
            Required height in pixels
        """
        if not self._parameter_form:
            return 100  # Fallback
        
        height = 0
        
        # Title height (use actual height or sizeHint)
        title_height = max(self._title_label.height(), self._title_label.sizeHint().height(), 24)
        height += title_height
        
        # Spacing after title
        height += self._layout.spacing()
        
        # Parameter form height - iterate through visible widgets
        form_layout = self._parameter_form.layout()
        visible_count = 0
        
        if form_layout:
            for i in range(form_layout.count()):
                item = form_layout.itemAt(i)
                if item and item.widget() and item.widget().isVisible():
                    widget = item.widget()
                    
                    # Use sizeHint, minimumSizeHint, or minimum fallback
                    widget_height = widget.sizeHint().height()
                    if widget_height <= 0:
                        widget_height = widget.minimumSizeHint().height()
                    if widget_height <= 0:
                        widget_height = self.MIN_PARAM_HEIGHT
                    
                    height += widget_height
                    visible_count += 1
                    
                    # Add spacing between widgets
                    if i < form_layout.count() - 1:
                        height += form_layout.spacing()
            
            # Add form margins
            form_margins = form_layout.contentsMargins()
            height += form_margins.top() + form_margins.bottom()
        
        # Panel margins
        margins = self._layout.contentsMargins()
        height += margins.top() + margins.bottom()
        
        # Extra buffer for safety
        height += 40
        
        return max(height, 100)  # Never return less than 100px
    
    def show_animated(self):
        """Animate panel to show content."""
        from client.gui.animators.animation_driver import AnimationDriver
        
        # Make visible if hidden
        was_hidden = not self.isVisible()
        if was_hidden:
            self.setMaximumHeight(0)
            self.show()
        
        # Get current height
        current_height = 0 if was_hidden else self.height()
        
        # Force layout update before calculating height
        if self._parameter_form:
            self._parameter_form.adjustSize()
            self._parameter_form.updateGeometry()
        self.adjustSize()
        self.updateGeometry()
        
        # Use QTimer to ensure layout is complete before animating
        def start_animation():
            target_height = self._calculate_content_height()
            
            # Stop any existing animation
            if self._animation:
                self._animation.stop()
                try:
                    self._animation.finished.disconnect()
                except:
                    pass
            
            # Create animation
            self._animation = QPropertyAnimation(self, b"maximumHeight")
            self._animation.setDuration(self.ANIM_DURATION)
            self._animation.setStartValue(current_height)
            self._animation.setEndValue(target_height)
            
            # Apply easing curve
            easing_type = AnimationDriver.EASING_MAP.get(
                self.EASING_CURVE, 
                QEasingCurve.Type.OutCubic
            )
            self._animation.setEasingCurve(easing_type)
            
            self._animation.start()
        
        # Small delay for layout to settle
        QTimer.singleShot(10, start_animation)
    
    def hide_animated(self):
        """Animate panel to hide."""
        from client.gui.animators.animation_driver import AnimationDriver
        
        if not self.isVisible():
            return
        
        # Stop any existing animation
        if self._animation:
            self._animation.stop()
            try:
                self._animation.finished.disconnect()
            except:
                pass
        
        # Create animation
        self._animation = QPropertyAnimation(self, b"maximumHeight")
        self._animation.setDuration(self.ANIM_DURATION)
        self._animation.setStartValue(self.height())
        self._animation.setEndValue(0)
        
        # Apply easing curve (use InCubic for closing)
        easing_type = AnimationDriver.EASING_MAP.get(
            "InCubic", 
            QEasingCurve.Type.InCubic
        )
        self._animation.setEasingCurve(easing_type)
        
        # Hide when animation finishes
        self._animation.finished.connect(self.hide)
        self._animation.start()
