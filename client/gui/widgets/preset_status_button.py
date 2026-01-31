"""
PresetStatusButton - Advanced Preset Button component.
Extracted from custom_widgets.py.
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtProperty, QPropertyAnimation, QRect, QPoint
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import QColor, QPainter, QBrush, QImage, QPixmap, QFont, QPen, QFontMetrics, QPainterPath

from client.gui.animators.animation_driver import AnimationDriver
from client.gui.effects.glow_effect import GlowEffectManager, GlowState
from client.utils.font_manager import FONT_FAMILY


class PresetStatusButton(QWidget):
    """
    Advanced Preset Button component.
    Handles dynamic width transitions and styling states (Ghost vs Solid).
    Features a Siri-style pulsating glow effect.
    """
    clicked = pyqtSignal()
    
    # Constants
    MIN_WIDTH = 150  # Minimum to fit "PRESETS" text
    MAX_WIDTH = 359  # Max for longer preset names
    PADDING = 60  # 30px left + 30px right for wider look
    ANIM_DURATION = 250 # Width animation duration (ms)
    
    # ==================== BUTTON NOISE CONFIGURATION ====================
    # Anti-banding noise applied to the button's solid background
    # This is separate from GlowNoiseOverlay which handles the blurred glow area
    
    # Opacity of the button's internal noise layer (0-255)
    # Recommended: 10-20 for subtle effect, higher if button has gradient fill
    NOISE_OPACITY = 15
    
    # Size of noise texture tile for button (pixels)
    NOISE_TILE_SIZE = 64
    
    # Noise intensity for button background
    NOISE_INTENSITY = 30
    # ====================================================================
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # Allow key events for debug
        self.setFixedHeight(48)
        
        # State
        self._text = "PRESETS"
        self._is_active = False  # False = Ghost, True = Solid
        self._is_hovered = False
        self._bg_color = QColor(255, 255, 255, 12)  # Ghost default
        self._text_color = QColor(255, 255, 255, 150)  # Inactive text
        self._current_width = self.MIN_WIDTH
        self._temp_shrink = False
        
        # Generate noise texture once for anti-banding
        self._noise_pixmap = self._generate_noise_texture()
        
        # Track theme for hover text color
        from client.utils.theme_utils import is_dark_mode
        self._is_dark = is_dark_mode()
        
        # Glow Effect Manager
        self._glow_manager = None
        
        # Animation State
        # Animation State
        self.width_easing_type = 'InOutCirc'
        self.anim_amplitude = 0.00
        self.anim_period = 0.00
        self.anim_overshoot = 1.70
        
        # Width animation
        self._width_anim = QPropertyAnimation(self, b"animWidth", self)
        self._width_driver = AnimationDriver(self._width_anim, duration=self.ANIM_DURATION, easing=self.width_easing_type)
        self._width_driver.amplitude = self.anim_amplitude
        self._width_driver.period = self.anim_period
        self._width_driver.overshoot = self.anim_overshoot


        # Text Position Smoothing
        self.text_easing_type = 'OutQuad'
        self.text_anim_duration = 307
        self._text_center_x = 0.0
        self._text_pos_anim = QPropertyAnimation(self, b"textCenter", self)
        self._text_pos_driver = AnimationDriver(self._text_pos_anim, duration=self.text_anim_duration, easing=self.text_easing_type)
        
        # Text Opacity Animation
        self._text_opacity = 1.0
        self._pending_text = None
        self._pending_active = False

        self.text_fade_duration = 120
        self.text_fade_easing = 'InCubic'
        
        self._text_fade_anim = QPropertyAnimation(self, b"textOpacity", self)
        self._text_fade_driver = AnimationDriver(self._text_fade_anim, duration=self.text_fade_duration, easing=self.text_fade_easing)
        self._text_fade_anim.finished.connect(self._on_fade_out_finished)
        
        # Click debounce flag
        self._click_pending = False
        
        # Calculate initial width
        # Calculate initial width
        self._calculate_and_set_initial_width()
        
        # Initial colors
        self._update_colors()
        
    def _update_colors(self):
        """Update instance colors based on state and theme"""
        if self._is_active:
             self._bg_color = QColor("#00AA00")
             # Text is always white on green background
             self._text_color = QColor(255, 255, 255, 255)
        else:
            if self._is_dark:
                self._bg_color = QColor(255, 255, 255, 12)
                self._text_color = QColor(255, 255, 255, 150) # Dim white
            else:
                self._bg_color = QColor(0, 0, 0, 12) # Dark ghost
                self._text_color = QColor(0, 0, 0, 150) # Dim black
        
    def mousePressEvent(self, event):
        """Handle mouse press - emit clicked signal with debounce."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Debounce: prevent multiple rapid clicks
            if self._click_pending:
                event.accept()
                return
            
            self._click_pending = True
            self.clicked.emit()
            if self._glow_manager:
                self._glow_manager.set_state(GlowState.CLICKED)
            event.accept()
            
            # Reset debounce after 300ms
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(300, self._reset_click_pending)
        else:
            super().mousePressEvent(event)
    
    def _reset_click_pending(self):
        """Reset the click debounce flag."""
        self._click_pending = False
    
    @pyqtProperty(float)
    def textCenter(self):
        return self._text_center_x
        
    @textCenter.setter
    def textCenter(self, x):
        self._text_center_x = x
        self.update()

    @pyqtProperty(float)
    def textOpacity(self):
        return self._text_opacity

    @textOpacity.setter
    def textOpacity(self, output):
        self._text_opacity = output
        self.update()
    

    
    def _generate_noise_texture(self):
        """
        Generate a static noise texture for the button background.
        Prevents banding on solid/gradient button fills.
        """
        from PyQt6.QtGui import QImage, QPixmap
        import random
        
        size = self.NOISE_TILE_SIZE
        intensity = self.NOISE_INTENSITY
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        
        # Bidirectional noise for natural film-grain effect
        for y in range(size):
            for x in range(size):
                noise_val = random.randint(-intensity, intensity)
                if noise_val > 0:
                    image.setPixelColor(x, y, QColor(255, 255, 255, noise_val))
                elif noise_val < 0:
                    image.setPixelColor(x, y, QColor(0, 0, 0, abs(noise_val)))
        
        return QPixmap.fromImage(image)
    
    def _setup_glow(self):
        """Create the glow effect manager"""
        if self._glow_manager is not None:
            return
            
        top_window = self.window()
        if top_window is None or top_window == self:
            return
            
        # Initialize the manager
        self._glow_manager = GlowEffectManager(self, top_window)
    
    def _update_glow_position(self):
        """Delegated to manager"""
        if self._glow_manager:
            self._glow_manager.update_position()
            
    def toggle_dev_panel(self):
        if not hasattr(self, '_param_panel'):
            from client.gui.effects.dev_panel import DevPanel
            
            # Create consolidated panel
            self._param_panel = DevPanel(title="Inspector - Preset Button")
            
            # --- Section 1: Button Properties ---
            btn_params = {
                'ANIM_DURATION': (100, 2000, 50),
                'MIN_WIDTH': (50, 200, 5),
                'MAX_WIDTH': (150, 400, 5),
                'PADDING': (0, 100, 2),
                'NOISE_OPACITY': (0, 255, 5),
                'NOISE_INTENSITY': (0, 100, 2),
            }
            def btn_change():
                self._width_driver.duration = self.ANIM_DURATION
                self._update_width()
                self.update()
            
            self._param_panel.add_section(
                target=self, 
                params=btn_params, 
                title="Button Logic", 
                source_file=r"v:\_MY_APPS\ImgApp_1\client\gui\custom_widgets.py",
                on_change=btn_change
            )
            
            # --- Section 2: Glow Effect ---
            if self._glow_manager and self._glow_manager._glow_overlay:
                glow = self._glow_manager._glow_overlay
                glow_params = {
                    'BLOB_RADIUS': (10, 150, 5),
                    'BLOB_OPACITY_CENTER': (0, 255, 5),
                    'BLOB_OPACITY_MID': (0, 255, 5),
                    'ELLIPSE_SCALE_X': (0.1, 1.5, 0.05, True),
                    'ELLIPSE_SCALE_Y': (0.1, 1.5, 0.05, True),
                    'PULSE_OPACITY_MIN': (0.0, 1.0, 0.05, True),
                    'PULSE_OPACITY_MAX': (0.0, 1.0, 0.05, True),
                    'MASK_PADDING': (0, 50, 1),
                    'MASK_CORNER_RADIUS': (0, 50, 1),
                    'MASK_FEATHER': (0, 50, 1),
                    'HOVER_MAX_OPACITY': (0.0, 1.0, 0.05, True),
                    'HOVER_FADE_IN_MS': (50, 1000, 50),
                    'HOVER_FADE_OUT_MS': (50, 1000, 50),
                }
                def glow_change(): 
                    glow.update()
                    
                self._param_panel.add_section(
                    target=glow,
                    params=glow_params,
                    title="Glow Overlay",
                    source_file=r"v:\_MY_APPS\ImgApp_1\client\gui\effects\glow_effect.py",
                    on_change=glow_change
                )
                
                # --- Section 3: Glow Animation ---
                anim_params = {
                    'animationEasing': (['OutBack', 'OutElastic', 'OutBounce', 'InOutQuad', 'OutCubic', 'Linear', 'OutExpo', 'InOutElastic'],),
                    'easingAmplitude': (0.0, 5.0, 0.1),
                    'easingPeriod': (0.0, 2.0, 0.05),
                }
                
                self._param_panel.add_section(
                    target=self._glow_manager,
                    params=anim_params,
                    title="Glow Animation",
                    source_file=r"v:\_MY_APPS\ImgApp_1\client\gui\effects\glow_effect.py",
                    on_change=lambda: None
                )
                
                # --- Section 4: Button Animation ---
                # --- Section 4: Button Animation ---
                # Use AnimationDriver for full control without hardcoding
                # Target 'self' so we can save changes to custom_widgets.py source
                anim_driver_params = {
                    'width_easing_type': (list(AnimationDriver.EASING_MAP.keys()),),
                    'ANIM_DURATION': (100, 2000, 50),
                    'anim_amplitude': (0.0, 5.0, 0.1),
                    'anim_period': (0.0, 2.0, 0.05),
                    'anim_overshoot': (0.0, 5.0, 0.1),
                }
                
                def apply_anim_changes():
                    # Push changes from self (Button) to Driver
                    self._width_driver.duration = self.ANIM_DURATION
                    self._width_driver.easing_type = self.width_easing_type
                    self._width_driver.amplitude = self.anim_amplitude
                    self._width_driver.period = self.anim_period
                    self._width_driver.overshoot = self.anim_overshoot
                    
                self._param_panel.add_section(
                    target=self,
                    params=anim_driver_params,
                    title="Button Animation (Driver)",
                    source_file=r"v:\_MY_APPS\ImgApp_1\client\gui\custom_widgets.py",
                    on_change=apply_anim_changes
                )

                # --- Section 5: Text Smoothing ---
                text_params = {
                    'text_easing_type': (list(AnimationDriver.EASING_MAP.keys()),),
                    'text_anim_duration': (100, 2000, 50),
                    'text_fade_easing': (list(AnimationDriver.EASING_MAP.keys()),),
                    'text_fade_duration': (50, 1000, 10),
                }

                def apply_text_changes():
                    # Positional Smoothing
                    self._text_pos_driver.easing_type = self.text_easing_type
                    self._text_pos_driver.duration = self.text_anim_duration
                    
                    # Opacity Fade
                    self._text_fade_driver.easing_type = self.text_fade_easing
                    self._text_fade_driver.duration = self.text_fade_duration

                self._param_panel.add_section(
                    target=self,
                    params=text_params,
                    title="Text Smoothing",
                    source_file=r"v:\_MY_APPS\ImgApp_1\client\gui\custom_widgets.py",
                    on_change=apply_text_changes
                )
            
        if self._param_panel.isVisible():
            self._param_panel.hide()
        else:
            self._param_panel.show()
            self._param_panel.raise_()

    def keyPressEvent(self, event):
        """Debug hook for effect tuning"""
        if event.key() == Qt.Key.Key_F12:
            self.toggle_dev_panel()
            return
        super().keyPressEvent(event)
            
    def moveEvent(self, event):
        """Update glow position when button moves"""
        super().moveEvent(event)
        self._update_glow_position()
    
    def resizeEvent(self, event):
        """Update glow position when button resizes"""
        super().resizeEvent(event)
        self._update_glow_position()
        
    def hideEvent(self, event):
        """Hide glow when button is hidden"""
        super().hideEvent(event)
        if self._glow_manager:
            self._glow_manager.hide()
            
    def showEvent(self, event):
        """Show/create glow when button is shown"""
        super().showEvent(event)
        if self._glow_manager is None:
            self._setup_glow()
        elif self._glow_manager:
            self._glow_manager.show()

    @pyqtProperty(int)
    def animWidth(self):
        return self._current_width
    
    @animWidth.setter
    def animWidth(self, w):
        self._current_width = w
        self.setFixedWidth(w)
        self._update_glow_position()
        self.update()
    
    def _calculate_and_set_initial_width(self):
        """Calculate and set initial width using the exact drawing font"""
        font = QFont()
        font.setFamily(FONT_FAMILY)
        font.setPixelSize(16)
        font.setWeight(QFont.Weight.DemiBold)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(self._text)
        initial_width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, text_width + self.PADDING))

        self._current_width = initial_width
        self._text_center_x = initial_width / 2.0  # Initialize center
        self.setFixedWidth(initial_width)
    
    def shrink_for_overlap(self, shrink):
        """Temporarily shrink button to make room for other widgets"""
        if self._temp_shrink == shrink:
            return
        self._temp_shrink = shrink
        self._update_width()
    
    def set_active(self, is_active, text="PRESETS"):
        """Set active state and text with fade animation"""
        new_text = text.upper()
        
        # If nothing changed, do nothing
        if self._text == new_text and self._is_active == is_active:
             return
             
        # Store pending state
        self._pending_active = is_active
        self._pending_text = new_text
        
        # Start Fade Out
        # We use the driver to ensure consistent behavior, but for opacity 
        # linear or quad is usually best.
        self._text_fade_driver.duration = self.text_fade_duration
        self._text_fade_driver.easing_type = self.text_fade_easing
        self._text_fade_driver.stop()
        self._text_fade_driver.setStartValue(self._text_opacity)
        self._text_fade_driver.setEndValue(0.0)
        self._text_fade_driver.start()
        
        # Start Width Animation concurrently (don't wait for fade out)
        # Use new_text to calculate target width
        self._update_width(text=new_text)
        
    def _on_fade_out_finished(self):
        """Called when text has faded out completely. Swap text and fade in."""
        if self._text_opacity > 0.01: # Use epsilon for float comparison
            # If we finished a Fade IN, do nothing
            return
            
        # Apply new state
        self._is_active = self._pending_active
        self._text = self._pending_text
        
        # Update Colors
        # Update Colors
        self._update_colors()
            
        # Start Fade In
        self._text_fade_driver.stop()
        self._text_fade_driver.setStartValue(0.0)
        self._text_fade_driver.setEndValue(1.0)
        self._text_fade_driver.start()
        
        self.update()
    
    def _update_width(self, text=None):
        """Update width based on text content"""
        target_text = text if text is not None else self._text
        
        if self._temp_shrink:
            target = self.MIN_WIDTH
        else:
            font = QFont()
            font.setFamily(FONT_FAMILY)
            font.setPixelSize(16)
            font.setWeight(QFont.Weight.DemiBold)
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(target_text)
            target = max(self.MIN_WIDTH, min(self.MAX_WIDTH, text_width + self.PADDING))
            
        if self.width() != target:
            # Animate Width
            self._width_driver.stop()
            self._width_driver.setStartValue(self.width())
            self._width_driver.setEndValue(target)
            self._width_driver.start()
            
            # Animate Text Center to new middle
            target_center = target / 2.0
            self._text_pos_driver.stop()
            self._text_pos_driver.setStartValue(self._text_center_x)
            self._text_pos_driver.setEndValue(target_center)
            self._text_pos_driver.start()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        radius = h / 2
        
        # Background with hover effect
        # Background with hover effect
        bg = self._bg_color
        if self._is_hovered and not self._is_active:
            # Ghost Hover
            if self._is_dark:
                bg = QColor(255, 255, 255, 25)
            else:
                bg = QColor(0, 0, 0, 0)  # Transparent in Light Mode
        elif self._is_hovered and self._is_active:
            bg = self._bg_color.lighter(110)

        painter.setBrush(QBrush(bg))
        
        # Border (Ghost only)
        if not self._is_active:
            if self._is_dark:
                border_color = QColor(255, 255, 255, 50)
                if self._is_hovered:
                    border_color = QColor(255, 255, 255, 100)
            else:
                border_color = QColor(0, 0, 0, 30)
                if self._is_hovered:
                    border_color = QColor(0, 0, 0, 80)
            painter.setPen(QPen(border_color, 1))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            
        painter.drawRoundedRect(1, 1, w-2, h-2, int(radius), int(radius))
        
        # Apply noise grain to prevent gradient banding
        # Clip to rounded rect shape, draw tiled noise, then restore
        if self._noise_pixmap and self.NOISE_OPACITY > 0:
            path = QPainterPath()
            path.addRoundedRect(1.0, 1.0, float(w-2), float(h-2), radius, radius)
            painter.setClipPath(path)
            painter.setOpacity(self.NOISE_OPACITY / 255.0)
            painter.drawTiledPixmap(self.rect(), self._noise_pixmap)
            painter.setOpacity(1.0)
            painter.setClipping(False)
        
        # Text
        text_color = QColor(self._text_color)
        
        # Override text color on hover if not active
        if self._is_hovered and not self._is_active:
            # Dark Mode -> White Text on Hover
            # Light Mode -> Black Text on Hover
            if self._is_dark:
                text_color = QColor(255, 255, 255, 255)
            else:
                text_color = QColor(0, 0, 0, 255)
                
        # Apply opacity animation
        text_color.setAlphaF(text_color.alphaF() * self._text_opacity)
        
        painter.setPen(text_color)
        font = self.font()
        font.setFamily(FONT_FAMILY)
        font.setWeight(QFont.Weight.DemiBold if self._is_active else QFont.Weight.Medium)
        font.setPixelSize(16)
        painter.setFont(font)
        
        # Draw text centered without elision/truncation
        # Draw text centered at smoothed position
        # Create a rect of same size, centered at (text_center_x, h/2)
        text_rect = QRect(0, 0, w, h)
        text_rect.moveCenter(QPoint(int(self._text_center_x), int(h/2)))
        
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._text)
    
    
    def enterEvent(self, event):
        self._is_hovered = True
        if self._glow_manager:
            self._glow_manager.set_state(GlowState.HOVER)
        self.update()
    
    def leaveEvent(self, event):
        self._is_hovered = False
        if self._glow_manager:
            self._glow_manager.set_state(GlowState.IDLE)
        self.update()
    
    def deleteLater(self):
        """Clean up glow manager"""
        if self._glow_manager:
            self._glow_manager.cleanup()
        super().deleteLater()
    
    def update_theme(self, is_dark):
        """Update theme state."""
        self._is_dark = is_dark
        self._update_colors()
        self.update()
