"""
Side Panel Animator - Mediator-Shell Architecture Component

Encapsulates spring-based side panel open/close animations.
Extracted from MainWindow to follow the Mediator-Shell pattern.
"""

from PyQt6.QtCore import QVariantAnimation, QEasingCurve, QTimer
from PyQt6.QtWidgets import QSplitter, QWidget


class SidePanelAnimator:
    """
    Encapsulates spring-based side panel open/close animations.
    
    Premium Animation Features:
    - Weighted motion with spring overshoot (OutBack easing)
    - Separate timing/easing for show vs hide
    - MaximumWidth constraint prevents layout "pop" artifact
    - Staggered side button reveal at configurable threshold
    - Sequential hide: buttons first, then panel
    
    Usage:
        animator = SidePanelAnimator(splitter, command_panel, right_frame)
        animator.open()   # Slide panel in
        animator.close()  # Slide panel out
        animator.toggle() # Toggle between states
    """
    
    # -------------------------------------------------------------------------
    # ANIMATION CONFIGURATION
    # -------------------------------------------------------------------------
    
    # Panel Size
    PANEL_TARGET_RATIO = 0.4  # Right panel takes 40% of total splitter width
    
    # Panel Timing (milliseconds)
    PANEL_SHOW_DURATION_MS = 450   # Slide-in duration (snappy entrance)
    PANEL_HIDE_DURATION_MS = 500   # Slide-out duration (snappy exit with weight)
    
    # Panel Easing Curve Options:
    #   "Linear", "OutQuad", "OutCubic", "OutExpo", "OutBack", "OutElastic"
    PANEL_SHOW_EASING = "OutBack"   # Premium weighted entrance
    PANEL_HIDE_EASING = "OutBack"   # Weighted exit with subtle overshoot
    
    # Panel Spring Parameters (only applies to OutBack easing)
    PANEL_SPRING_OVERSHOOT = 0.7   # 0.0 = no spring, 1.7 = default, 0.5-0.8 = subtle
    PANEL_HIDE_OVERSHOOT = 0.5     # Overshoot for hide animation (more subtle than show)
    
    # -------------------------------------------------------------------------
    # SIDE BUTTONS STAGGERED ANIMATION
    # -------------------------------------------------------------------------
    
    # ---- SHOW Animation ----
    BUTTONS_REVEAL_THRESHOLD = 0.9  # When to start showing buttons (0.0 - 1.0)
    BUTTONS_SHOW_STAGGER_MS = 60    # Stagger delay between buttons
    BUTTONS_SHOW_DURATION_MS = 200  # Button show animation duration
    BUTTONS_SHOW_EASING = "OutCubic"
    
    # ---- HIDE Animation ----
    BUTTONS_HIDE_DURATION_MS = 100
    BUTTONS_HIDE_EASING = "InQuad"
    BUTTONS_HIDE_HEAD_START_MS = 200  # Delay before panel slides out
    
    # -------------------------------------------------------------------------
    # EASING CURVE MAP
    # -------------------------------------------------------------------------
    EASING_MAP = {
        "Linear": QEasingCurve.Type.Linear,
        "OutQuad": QEasingCurve.Type.OutQuad,
        "OutCubic": QEasingCurve.Type.OutCubic,
        "OutExpo": QEasingCurve.Type.OutExpo,
        "OutBack": QEasingCurve.Type.OutBack,
        "OutElastic": QEasingCurve.Type.OutElastic,
        "InOutCubic": QEasingCurve.Type.InOutCubic,
        "InQuad": QEasingCurve.Type.InQuad,
        "InCubic": QEasingCurve.Type.InCubic,
    }
    
    def __init__(self, splitter: QSplitter, command_panel: QWidget, right_frame: QWidget):
        """
        Initialize the side panel animator.
        
        Args:
            splitter: The QSplitter containing left and right panels
            command_panel: The command panel widget
            right_frame: The right frame container widget
        """
        self.splitter = splitter
        self.command_panel = command_panel
        self.right_frame = right_frame
        
        # Animation state
        self._panel_anim = None
        self._buttons_triggered = False
        self._is_open = False
        
        # Callback for button animations (injected by MainWindow)
        self._on_buttons_show = None
        self._on_buttons_hide = None
    
    @property
    def is_open(self) -> bool:
        """Return whether the panel is currently open."""
        return self._is_open
    
    def set_button_callbacks(self, on_show, on_hide):
        """
        Set callbacks for button animation events.
        
        Args:
            on_show: Callback when buttons should reveal (hide=False)
            on_hide: Callback when buttons should hide (hide=True)
        """
        self._on_buttons_show = on_show
        self._on_buttons_hide = on_hide
    
    def open(self):
        """Animate panel to open position (slide in from right)."""
        if self._is_open:
            return
        self._toggle(show=True)
    
    def close(self):
        """Animate panel to closed position (slide out to right)."""
        if not self._is_open:
            return
        self._toggle(show=False)
    
    def toggle(self):
        """Toggle between open and closed states."""
        self._toggle(show=not self._is_open)
    
    def _toggle(self, show: bool):
        """
        Animate Command Panel sliding in/out from the RIGHT edge.
        
        Args:
            show: True to slide panel in, False to slide it out
        """
        # Early exit if already in the requested state
        if show == self.right_frame.isVisible() and self._is_open == show:
            return
        
        self._is_open = show
        
        # Stop any running animation
        if self._panel_anim and self._panel_anim.state() == QVariantAnimation.State.Running:
            self._panel_anim.stop()
        
        # Calculate dimensions
        current_sizes = self.splitter.sizes()
        total_width = sum(current_sizes)
        target_right_width = int(total_width * self.PANEL_TARGET_RATIO)
        
        # Track whether we've triggered side buttons
        self._buttons_triggered = False
        
        if show:
            # SHOWING: Panel slides in from right edge (0 → target width)
            self.right_frame.setMaximumWidth(0)
            self.right_frame.setVisible(True)
            self.splitter.setSizes([total_width, 0])
            
            start_width = 0
            end_width = target_right_width
            duration = self.PANEL_SHOW_DURATION_MS
            easing_name = self.PANEL_SHOW_EASING
            
            # Start panel animation immediately for show
            self._start_animation(show, start_width, end_width, duration, 
                                  easing_name, total_width, target_right_width)
        else:
            # HIDING: Sequential animation - buttons first, then panel
            if self._on_buttons_hide:
                self._on_buttons_hide()
            
            # Schedule panel to slide out AFTER buttons reach panel edge
            start_width = current_sizes[1]
            end_width = 0
            duration = self.PANEL_HIDE_DURATION_MS
            easing_name = self.PANEL_HIDE_EASING
            
            QTimer.singleShot(
                self.BUTTONS_HIDE_HEAD_START_MS,
                lambda: self._start_animation(show, start_width, end_width, 
                                              duration, easing_name, total_width, 
                                              target_right_width)
            )
    
    def _start_animation(self, show: bool, start_width: int, end_width: int, 
                         duration: int, easing_name: str, total_width: int, 
                         target_right_width: int):
        """
        Internal helper to start the panel slide animation.
        """
        # Stop any running animation
        if self._panel_anim and self._panel_anim.state() == QVariantAnimation.State.Running:
            self._panel_anim.stop()
        
        # Create and configure animation
        self._panel_anim = QVariantAnimation()
        self._panel_anim.setDuration(duration)
        
        # Build easing curve with optional spring parameters
        easing_type = self.EASING_MAP.get(easing_name, QEasingCurve.Type.OutQuad)
        easing_curve = QEasingCurve(easing_type)
        
        # Apply spring overshoot for OutBack easing
        if easing_name == "OutBack":
            overshoot = self.PANEL_SPRING_OVERSHOOT if show else self.PANEL_HIDE_OVERSHOOT
            easing_curve.setOvershoot(overshoot)
        
        self._panel_anim.setEasingCurve(easing_curve)
        self._panel_anim.setStartValue(start_width)
        self._panel_anim.setEndValue(end_width)
        
        # Capture state for closures
        animator = self
        
        def on_value_changed(right_width):
            # Update the maximum width constraint to match animated value
            animator.right_frame.setMaximumWidth(max(0, right_width))
            
            # Recalculate total width dynamically to handle layout shifts from button animations
            current_sizes = animator.splitter.sizes()
            current_total = sum(current_sizes)
            
            # Update splitter proportions using current total width
            left_width = current_total - right_width
            animator.splitter.setSizes([left_width, right_width])
            
            # Staggered side buttons reveal (only during show)
            if show and not animator._buttons_triggered:
                progress = right_width / target_right_width if target_right_width > 0 else 0
                if progress >= animator.BUTTONS_REVEAL_THRESHOLD:
                    animator._buttons_triggered = True
                    if animator._on_buttons_show:
                        animator._on_buttons_show()
        
        self._panel_anim.valueChanged.connect(on_value_changed)
        
        def on_animation_finished():
            if show:
                # Ensure final sizes are set correctly before removing constraint
                current_sizes = animator.splitter.sizes()
                current_total = sum(current_sizes)
                final_left = current_total - target_right_width
                animator.splitter.setSizes([final_left, target_right_width])
                
                # Remove the maximum width constraint
                animator.right_frame.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
                
                # Ensure buttons are visible if animation finished before threshold
                if not animator._buttons_triggered and animator._on_buttons_show:
                    animator._on_buttons_show()
            else:
                # Hide the panel completely
                animator.right_frame.setVisible(False)
        
        self._panel_anim.finished.connect(on_animation_finished)
        
        # Start the animation
        self._panel_anim.start()
    
    # -------------------------------------------------------------------------
    # BUTTON ANIMATION METHODS (Extracted from MainWindow)
    # -------------------------------------------------------------------------
    
    def trigger_side_buttons_animation(self, hide: bool = False):
        """
        Trigger staggered animation for ALL Command Panel Side Buttons.
        
        Button Groups (animated top to bottom):
        1. Command Panel Main Folder Buttons: Max Size, Lab Presets, Manual
        2. Command Panel Transform Folder Buttons: Resize, Rotate, Time (tab-dependent)
        
        SHOW: Buttons reveal with stagger delay (one after another)
        HIDE: All buttons hide simultaneously (no stagger)
        
        Args:
            hide: True to hide buttons, False to reveal them
        """
        if not hasattr(self, 'command_panel') or self.command_panel is None:
            return
        
        # Collect ALL buttons in ORDER (top to bottom)
        all_buttons = []
        
        # --- 1. Main Folder Buttons (ModeButtonsWidget) ---
        if hasattr(self.command_panel, 'mode_buttons'):
            mode_btns = self.command_panel.mode_buttons
            if hasattr(mode_btns, 'max_size_btn'):
                all_buttons.append(mode_btns.max_size_btn)
            if hasattr(mode_btns, 'presets_btn'):
                all_buttons.append(mode_btns.presets_btn)
            if hasattr(mode_btns, 'manual_btn'):
                all_buttons.append(mode_btns.manual_btn)
        
        # --- 2. Transform Folder Buttons (SideButtonGroup) ---
        current_tab = self.command_panel.tabs.currentIndex() if hasattr(self.command_panel, 'tabs') else 0
        
        transform_group = None
        if current_tab == 0 and hasattr(self.command_panel, 'image_side_buttons'):
            transform_group = self.command_panel.image_side_buttons
        elif current_tab == 1 and hasattr(self.command_panel, 'video_side_buttons'):
            transform_group = self.command_panel.video_side_buttons
        elif current_tab == 2 and hasattr(self.command_panel, 'loop_side_buttons'):
            transform_group = self.command_panel.loop_side_buttons
        
        if transform_group and hasattr(transform_group, 'buttons'):
            if hasattr(transform_group, 'buttons_config'):
                for config in transform_group.buttons_config:
                    btn_id = config.get('id', '')
                    if btn_id in transform_group.buttons:
                        all_buttons.append(transform_group.buttons[btn_id])
            else:
                all_buttons.extend(transform_group.buttons.values())
        
        # --- Trigger animation ---
        if hide:
            for btn in all_buttons:
                self._hide_button(btn)
        else:
            for i, btn in enumerate(all_buttons):
                delay = i * self.BUTTONS_SHOW_STAGGER_MS
                QTimer.singleShot(delay, lambda b=btn: self._reveal_button(b))
    
    def _reveal_button(self, btn):
        """Reveal a single side button with animation."""
        if hasattr(btn, 'set_force_hidden'):
            if hasattr(btn, 'animation'):
                easing = self.EASING_MAP.get(self.BUTTONS_SHOW_EASING, QEasingCurve.Type.OutCubic)
                btn.animation.setDuration(self.BUTTONS_SHOW_DURATION_MS)
                btn.animation.setEasingCurve(easing)
            btn.set_force_hidden(False)
    
    def _hide_button(self, btn):
        """Hide a single side button with animation."""
        if hasattr(btn, 'set_force_hidden'):
            if hasattr(btn, 'animation'):
                easing = self.EASING_MAP.get(self.BUTTONS_HIDE_EASING, QEasingCurve.Type.InQuad)
                btn.animation.setDuration(self.BUTTONS_HIDE_DURATION_MS)
                btn.animation.setEasingCurve(easing)
            btn.set_force_hidden(True)
