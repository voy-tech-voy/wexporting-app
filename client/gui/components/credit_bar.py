"""
Credit Bar Component
Procedural geometry visualization for Energy credits.
Vertical bars with sine-wave modulated Y-position.
"""

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QTimer, QSize, Property, Slot, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont
import math

from client.gui.theme import Theme

class CreditBarArchive(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(40)
        self.setMinimumWidth(100)
        
        # Parameters
        self._amplitude = 5.0
        self._frequency = 2.0
        self._phase = 0.0
        self._bar_count = 50
        self._bar_ratio = 13.0  # H:W ratio
        
        # Holographic Parameters
        self._saturation = 0.8
        self._transparency = 0.9
        self._noise = 0.0
        self._horizontal_offset = 0.5 # 0.0=Left, 0.5=Center, 1.0=Right
        
        # New Visual Params
        self._active_saturation = 1.0
        self._active_transparency = 1.0  # Separate transparency for filled bars
        self._current_credits = 750
        self._max_credits = 1000
        
        # Holographic Color Effects
        self._hue_shift = 0.0  # 0.0-1.0: Iridescent color shift
        self._chromatic_aberration = 0.0  # 0.0-1.0: RGB channel separation
        self._glow_intensity = 0.0  # 0.0-1.0: Bloom/glow effect
        self._shimmer_speed = 0.0  # 0.0-1.0: Animation speed for shimmer
        self._gain = 1.0  # 0.0-2.0: Overall brightness multiplier
        
        # Persistence
        import os
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        self._config_file = os.path.join(app_data, 'wexporting', 'config', 'credit_bar.json')
        
        # Visuals
        # Visuals
        self._fixed_font = QFont(Theme.FONT_BODY, Theme.FONT_SIZE_BASE)
        self._fixed_font.setBold(False)
        self.setFont(self._fixed_font)
        
        self._color_primary = QColor("#00E0FF") # Cyan
        self._color_secondary = QColor("#0088FF") # Blue
        
        # Interaction
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._dev_panel = None
        
        # Load Config
        QTimer.singleShot(0, self.load_config)

    def mousePressEvent(self, event):
        self.setFocus()
        self.update() # Visual feedback
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)
            
    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)
        
    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)
    
    def update_theme(self, is_dark: bool):
        """Handle theme changes to prevent layout issues"""
        # Enforce fixed font to prevent stylesheet inheritance issues
        self.setFont(self._fixed_font)
        # Force a complete repaint
        self.update()
        # Ensure geometry is recalculated
        self.updateGeometry()
    
    @Property(float)
    def amplitude(self): return self._amplitude

    @amplitude.setter
    def amplitude(self, value):
        self._amplitude = value
        self.update()
        
    @Property(float)
    def frequency(self): return self._frequency
    
    @frequency.setter
    def frequency(self, value):
        self._frequency = value
        self.update()
        
    @Property(float)
    def phase(self): return self._phase
    
    @phase.setter
    def phase(self, value):
        self._phase = value
        self.update()
        
    @Property(int)
    def bar_count(self): return self._bar_count
    
    @bar_count.setter
    def bar_count(self, value):
        self._bar_count = value
        self.update()

    @Property(float)
    def saturation(self): return self._saturation
    
    @saturation.setter
    def saturation(self, value):
        self._saturation = max(0.0, min(1.0, value))
        self.update()

    @Property(float)
    def transparency(self): return self._transparency
    
    @transparency.setter
    def transparency(self, value):
        self._transparency = max(0.0, min(1.0, value))
        self.update()

    @Property(float)
    def noise(self): return self._noise
    
    @noise.setter
    def noise(self, value):
        self._noise = max(0.0, min(1.0, value))
        self.update()
        
    @Property(float)
    def horizontal_offset(self): return self._horizontal_offset
    
    @horizontal_offset.setter
    def horizontal_offset(self, value):
        self._horizontal_offset = max(0.0, min(1.0, value))
        self.update()

    @Property(float)
    def active_saturation(self): return self._active_saturation
    
    @active_saturation.setter
    def active_saturation(self, value):
        self._active_saturation = max(0.0, min(1.0, value))
        self.update()

    @Property(float)
    def noise(self): return self._noise
    
    @noise.setter
    def noise(self, value):
        self._noise = max(0.0, min(1.0, value))
        self.update()
        
    @Property(int)
    def current_credits(self): return self._current_credits
    
    @current_credits.setter
    def current_credits(self, value):
        self._current_credits = value
        self.update()
        
    @Property(int)
    def max_credits(self): return self._max_credits
    
    @max_credits.setter
    def max_credits(self, value):
        self._max_credits = value
        self.update()
        
    @Property(float)
    def active_transparency(self): return self._active_transparency
    
    @active_transparency.setter
    def active_transparency(self, value):
        self._active_transparency = max(0.0, min(1.0, value))
        self.update()
        
    @Property(float)
    def hue_shift(self): return self._hue_shift
    
    @hue_shift.setter
    def hue_shift(self, value):
        self._hue_shift = max(0.0, min(1.0, value))
        self.update()
        
    @Property(float)
    def chromatic_aberration(self): return self._chromatic_aberration
    
    @chromatic_aberration.setter
    def chromatic_aberration(self, value):
        self._chromatic_aberration = max(0.0, min(1.0, value))
        self.update()
        
    @Property(float)
    def glow_intensity(self): return self._glow_intensity
    
    @glow_intensity.setter
    def glow_intensity(self, value):
        self._glow_intensity = max(0.0, min(1.0, value))
        self.update()
        
    @Property(float)
    def shimmer_speed(self): return self._shimmer_speed
    
    @shimmer_speed.setter
    def shimmer_speed(self, value):
        self._shimmer_speed = max(0.0, min(1.0, value))
        self.update()
        
    @Property(float)
    def gain(self): return self._gain
    
    @gain.setter
    def gain(self, value):
        self._gain = max(0.0, min(2.0, value))
        self.update()
        
    def load_config(self):
        import json, os
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, 'r') as f:
                    data = json.load(f)
                    self._amplitude = data.get('amplitude', self._amplitude)
                    self._frequency = data.get('frequency', self._frequency)
                    self._phase = data.get('phase', self._phase)
                    self._bar_count = int(data.get('bar_count', self._bar_count))
                    self._saturation = data.get('saturation', self._saturation)
                    self._active_saturation = data.get('active_saturation', self._active_saturation)
                    self._transparency = data.get('transparency', self._transparency)
                    self._active_transparency = data.get('active_transparency', self._active_transparency)
                    self._noise = data.get('noise', self._noise)
                    self._horizontal_offset = data.get('horizontal_offset', self._horizontal_offset)
                    self._hue_shift = data.get('hue_shift', self._hue_shift)
                    self._chromatic_aberration = data.get('chromatic_aberration', self._chromatic_aberration)
                    self._glow_intensity = data.get('glow_intensity', self._glow_intensity)
                    self._shimmer_speed = data.get('shimmer_speed', self._shimmer_speed)
                    self._gain = data.get('gain', self._gain)
                    self.update()
        except Exception as e:
            print(f"Error loading CreditBar config: {e}")

    def save_config(self):
        import json, os
        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            data = {
                'amplitude': self._amplitude,
                'frequency': self._frequency,
                'phase': self._phase,
                'bar_count': self._bar_count,
                'saturation': self._saturation,
                'active_saturation': self._active_saturation,
                'transparency': self._transparency,
                'active_transparency': self._active_transparency,
                'noise': self._noise,
                'horizontal_offset': self._horizontal_offset,
                'hue_shift': self._hue_shift,
                'chromatic_aberration': self._chromatic_aberration,
                'glow_intensity': self._glow_intensity,
                'shimmer_speed': self._shimmer_speed,
                'gain': self._gain
            }
            with open(self._config_file, 'w') as f:
                json.dump(data, f, indent=4)
            print("CreditBar config saved.")
        except Exception as e:
            print(f"Error saving CreditBar config: {e}")
    
    def set_credits(self, current, max_credits):
        """Update credit values from EnergyManager"""
        self._current_credits = current
        self._max_credits = max_credits
        self.update()

    def sizeHint(self):
        # Calculate ideal width based on height and count
        h = 50 # Assumption
        if self.parent():
            h = self.parent().height() - 16 # Padding
            
        w_per_bar = h / self._bar_ratio
        total_w = w_per_bar * self._bar_count
        return QSize(int(total_w), int(h))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Available area
        w = self.width()
        h = self.height()
        
        # Calculate max potential height of the wave + bars
        # Max excursion = amplitude + (bar_height / 2)
        # We need to map this to available height 'h'
        
        # Base bar height (unscaled)
        # We'll use a normalized coordinate system first
        # Let's say max_amp = self._amplitude
        # We need to fit (2 * max_amp) + bar_height into h?
        # Actually, the user wants the entire visualization to scale.
        
        # Let's derive scale factor.
        # Max Y extent relative to center = Amplitude + (BarHeight/2)
        # We want (Amplitude + BarHeight/2) * 2 <= h (if centered)
        # But BarHeight depends on aspect ratio...
        
        # Let's fix the aspect ratio relation: H_bar = W_bar * 13
        # W_bar * Count ~= W_total
        # So H_bar is roughly proportional to W_total if we fill width.
        
        # Strategy:
        # 1. Determine maximum possible bar height if we use full width
        #    bar_w_ideal = w / self._bar_count
        #    bar_h_ideal = bar_w_ideal * self._bar_ratio
        #
        # 2. Determine scale factor to fit height
        #    required_h = (self._amplitude * 2) + bar_h_ideal
        #    scale = min(1.0, h / required_h)
        #
        # 3. Apply scale
        
        if self._bar_count <= 0: return
        
        # Hybrid Sizing (Stable & Full-Width)
        # 1. Bar Width: derived from container WIDTH (to fill space)
        #    This ensures "proper width" as requested by user.
        bar_w = w / self._bar_count
        
        # 2. Bar Height: derived from container HEIGHT (to ensure stability)
        #    This decouples height from width changes (preventing aspect ratio scaling issues)
        #    We use 50% of height as base bar height, allowing room for wave amplitude
        bar_h = h * 0.5 
        
        # Calculate scale to fit HEIGHT (amplitude containment)
        total_span = (self._amplitude * 2) + bar_h
        
        # Scale only if we exceed height (to prevent clipping)
        scale = 1.0
        if total_span > h:
            scale = h / total_span
            
        # Debug prints removed for production
        # print(f"DEBUG_PAINT: w={w}, h={h}, scale={scale:.3f}, bar_w={bar_w:.3f}...")
            
        # Apply scale to dimensions
        # effective_amp = self._amplitude * scale
        # effective_bar_h = bar_h * scale
        # effective_bar_w = bar_w * scale (to maintain aspect ratio)
        
        # BUT if we scale bar_w, we affect total width coverage.
        # The user said "size of the bar shoul automatically scale".
        # If we shrink bar_w, we get gaps or we must use narrower total width.
        # Let's stick with "bars touching" -> Total width is maintained?
        # If total width maintained, then bar_w is fixed.
        # Then bar_h must be fixed (due to ratio).
        # Then we can only scale Amplitude?
        # OR we scale everything and center horizontally.
        
        # "so when i adjust amplitude it adjusts scale overall too"
        # This implies shrinking the whole drawing to fit.
        
        effective_w = bar_w * scale
        effective_h = bar_h * scale
        effective_amp = self._amplitude * scale
        
        # Text Overlay
        painter.setFont(self._fixed_font)
        text_str = f"{self._current_credits}/{self._max_credits}"
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(text_str)
        text_h = fm.height()
        padding = 10
        
        total_content_w = (effective_w * self._bar_count) + text_w + padding
        
        # Available space to move
        available_slack = w - total_content_w
        
        # Start X (Group)
        start_x_group = available_slack * self._horizontal_offset
        
        # Draw Text
        # Align vertically center
        text_y = (h - text_h) / 2
        text_rect = QRectF(start_x_group, 0, text_w, h)
        
        # Text color based on theme or white with transparency
        text_color = QColor(255, 255, 255, int(255 * 0.9))
        painter.setPen(text_color)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text_str)
        
        # Bar Start
        start_x = start_x_group + text_w + padding
        
        cy = h / 2
        
        painter.setPen(Qt.PenStyle.NoPen)
        
        for i in range(self._bar_count):
            u = i / (self._bar_count - 1) if self._bar_count > 1 else 0.5
            
            # Parametric Y offset (Sine Wave)
            wave = math.sin(u * self._frequency * math.pi * 2 + self._phase)
            y_off = wave * effective_amp
            
            # Position
            x = start_x + (i * effective_w)
            y = cy + y_off - (effective_h / 2)
            
            # Infrared Color Ramp (Blue -> Red via HSV)
            hue = (1.0 - u) * 0.66
            
            # Random Hue Variation (based on bar index noise)
            if self._noise > 0:
                # Use bar index as seed for consistent but varied hue shift
                hue_noise_seed = i * 7.919  # Prime number for better distribution
                hue_variation = math.sin(hue_noise_seed) * self._noise * 0.15
                hue = (hue + hue_variation) % 1.0
            
            # Holographic Hue Shift (Iridescence)
            if self._hue_shift > 0:
                # Shift hue based on position for rainbow effect
                hue_offset = (u + self._phase * 0.1) * self._hue_shift
                hue = (hue + hue_offset) % 1.0
            
            # Brightness/Alpha Noise (Holographic effect)
            val = 1.0
            alpha = self._transparency
            
            if self._noise > 0:
                # Deterministic noise based on position and phase
                noise_seed = i * 13.37 + self._phase * 5.0
                noise = math.sin(noise_seed) * self._noise
                
                # Modulate value (brightness)
                val = max(0.5, min(1.0, 1.0 - (noise * 0.3)))
                
                # Modulate alpha for shimmer
                alpha = max(0.1, min(1.0, self._transparency - (noise * 0.2)))
            
            # Shimmer Animation (time-based if speed > 0)
            if self._shimmer_speed > 0:
                import time
                shimmer_phase = (time.time() * self._shimmer_speed * 2.0) % (math.pi * 2)
                shimmer = math.sin(shimmer_phase + u * math.pi * 4) * 0.15
                val = max(0.3, min(1.0, val + shimmer))
            
            # Progress Logic
            progress = self._current_credits / max(1, self._max_credits)
            bar_idx_progress = i / max(1, self._bar_count)
            
            # Determine saturation and alpha based on active/inactive
            sat = self._active_saturation if bar_idx_progress <= progress else self._saturation
            final_alpha = self._active_transparency if bar_idx_progress <= progress else alpha
            
            # Glow Intensity (increase saturation and brightness)
            if self._glow_intensity > 0:
                sat = min(1.0, sat + self._glow_intensity * 0.3)
                val = min(1.0, val + self._glow_intensity * 0.2)
            
            # Apply Gain (brightness multiplier)
            val = min(1.0, val * self._gain)
            
            # Theme-aware brightness adjustment for light mode
            from client.gui.theme_manager import ThemeManager
            is_dark = ThemeManager.instance().is_dark_mode()
            if not is_dark:
                # In light mode, darken the bars significantly for visibility
                val = val * 0.4  # Reduce brightness to 40% in light mode
                sat = min(1.0, sat * 1.2)  # Increase saturation slightly
            
            # Create base color
            color = QColor.fromHsvF(hue, sat, val, final_alpha)
            
            # Chromatic Aberration (RGB channel separation)
            if self._chromatic_aberration > 0:
                # Offset for RGB channels
                offset = self._chromatic_aberration * 2.0
                
                # Draw red channel shifted
                r_color = QColor(color.red(), 0, 0, int(color.alpha() * 0.7))
                painter.setBrush(QBrush(r_color))
                painter.drawRect(QRectF(x - offset, y, effective_w, effective_h))
                
                # Draw green channel (center)
                g_color = QColor(0, color.green(), 0, int(color.alpha() * 0.7))
                painter.setBrush(QBrush(g_color))
                painter.drawRect(QRectF(x, y, effective_w, effective_h))
                
                # Draw blue channel shifted
                b_color = QColor(0, 0, color.blue(), int(color.alpha() * 0.7))
                painter.setBrush(QBrush(b_color))
                painter.drawRect(QRectF(x + offset, y, effective_w, effective_h))
            else:
                # Normal rendering
                painter.setBrush(QBrush(color))
                painter.drawRect(QRectF(x, y, effective_w, effective_h))
            

        # Draw focus indicator
        if self.hasFocus():
            painter.setPen(QPen(QColor("#FFFFFF"), 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(0, 0, w-1, h-1)


class CreditBar(QWidget):
    """
    New Credit Bar Component
    Displays energy credits as a thunderbolt icon that fills up.
    Format: [Current/Max] [Thunderbolt Icon]
    """
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(40)
        # self.setMinimumWidth(150) # Adjust based on text length + icon width
        
        self._current_credits = 750
        self._max_credits = 1000
        self._preview_cost: int | None = None

        self._fixed_font = QFont(Theme.FONT_BODY, Theme.FONT_SIZE_BASE)
        self._fixed_font.setBold(True)
        self.setFont(self._fixed_font)
        
        # Colors - Using Theme colors where possible, or fallbacks
        self._color_energy = Theme.color('accent_turbo') # Cyan/Electric
        self._color_empty = Theme.color('surface_element') # Dark/Empty background (Safe key)
        self._color_text = Theme.text_muted() # Greyed out text - use method, not key lookup
        
        # Visual Parameters
        self._filled_transparency = 1.0
        self._empty_transparency = 0.4
        self._gain = 1.0
        
        # Persistence
        import os
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        self._config_file = os.path.join(app_data, 'wexporting', 'config', 'credit_bar.json')
        
        # Dev panel
        self._dev_panel = None
        
        # Enable keyboard focus for F12
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        # Load Config
        QTimer.singleShot(0, self.load_config)

    def mousePressEvent(self, event):
        """Handle mouse press to gain focus and emit click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        self.setFocus()
        super().mousePressEvent(event)

    def load_config(self):
        import json, os
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, 'r') as f:
                    data = json.load(f)
                    self._filled_transparency = data.get('filled_transparency', self._filled_transparency)
                    self._empty_transparency = data.get('empty_transparency', self._empty_transparency)
                    self._gain = data.get('gain', self._gain)
                    self.update()
        except Exception as e:
            print(f"Error loading CreditBar config: {e}")

    def save_config(self):
        import json, os
        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            data = {
                'filled_transparency': self._filled_transparency,
                'empty_transparency': self._empty_transparency,
                'gain': self._gain
            }
            with open(self._config_file, 'w') as f:
                json.dump(data, f, indent=4)
            print("CreditBar config saved.")
        except Exception as e:
            print(f"Error saving CreditBar config: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F12:
            self._toggle_dev_panel()
            event.accept()
        else:
            super().keyPressEvent(event)
            
    def _toggle_dev_panel(self):
        if self._dev_panel is None or not self._dev_panel.isVisible():
            try:
                from client.gui.dev_credit_bar_panel import DevCreditBarPanel
                self._dev_panel = DevCreditBarPanel(self)
                self._dev_panel.show()
            except ImportError:
                print("DevCreditBarPanel not found")
        else:
            self._dev_panel.close()

    @Property(float)
    def filled_transparency(self): return self._filled_transparency
    
    @filled_transparency.setter
    def filled_transparency(self, value):
        self._filled_transparency = max(0.0, min(1.0, value))
        self.update()

    @Property(float)
    def empty_transparency(self): return self._empty_transparency
    
    @empty_transparency.setter
    def empty_transparency(self, value):
        self._empty_transparency = max(0.0, min(1.0, value))
        self.update()

    @Property(float)
    def gain(self): return self._gain
    
    @gain.setter
    def gain(self, value):
        self._gain = max(0.0, min(2.0, value))
        self.update()
    
    @Property(int)
    def current_credits(self): return self._current_credits
    
    @current_credits.setter
    def current_credits(self, value):
        self._current_credits = value
        self.update()
    
    @Property(int)
    def max_credits(self): return self._max_credits
    
    @max_credits.setter
    def max_credits(self, value):
        self._max_credits = value
        self.update()
        
    def set_preview_cost(self, cost: int):
        """Show a deduction preview on the credit text (hover state)."""
        self._preview_cost = cost
        self.update()

    def clear_preview_cost(self):
        """Restore normal credit display."""
        self._preview_cost = None
        self.update()

    def set_credits(self, current, max_credits):
        """Update credit values"""
        self._current_credits = current
        self._max_credits = max_credits
        self.update()
        
    def update_theme(self, is_dark: bool):
        """Handle theme changes"""
        # Update colors based on new theme state
        self._color_energy = Theme.color('accent_turbo')
        self._color_empty = Theme.color('surface_element')
        self._color_text = Theme.text_muted()
        self.update()
        
    def sizeHint(self):
        # Calculate width dynamically based on MAX POSSIBLE TEXT
        # This matches the fixed width logic in paintEvent (includes preview format)
        max_text_str = "9999-999/9999"

        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(max_text_str)
        
        icon_w = 24 # Width of thunderbolt (approx 18 + margin)
        padding = 12 # Spacing between text and icon
        
        # Add extra padding for safety
        return QSize(text_w + padding + icon_w + 10, 40)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        painter.setFont(self.font())

        # Layout
        icon_w = 22  # Slightly wider for better proportions
        icon_h = 28
        spacing = 10

        fm = painter.fontMetrics()

        # Fixed text width accommodates both normal ("9999/9999") and preview
        # ("9999-999/9999") formats so the thunderbolt icon never shifts.
        max_text_str = "9999-999/9999"
        fixed_text_w = fm.horizontalAdvance(max_text_str)

        is_preview = self._preview_cost is not None

        if is_preview:
            prefix_str = f"{self._current_credits}"
            deduct_str = f"-{self._preview_cost}"
            suffix_str = f"/{self._max_credits}"

            prefix_w = fm.horizontalAdvance(prefix_str)
            deduct_w = fm.horizontalAdvance(deduct_str)
            suffix_w = fm.horizontalAdvance(suffix_str)
            total_w = prefix_w + deduct_w + suffix_w

            # Right-align the composite text within fixed_text_w
            x = fixed_text_w - total_w

            painter.setPen(QColor(self._color_text))
            painter.drawText(QRectF(x, 0, prefix_w, h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, prefix_str)

            painter.setPen(QColor("#FF6B35"))
            painter.drawText(QRectF(x + prefix_w, 0, deduct_w, h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, deduct_str)

            painter.setPen(QColor(self._color_text))
            painter.drawText(QRectF(x + prefix_w + deduct_w, 0, suffix_w, h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, suffix_str)
        else:
            text_str = f"{self._current_credits}/{self._max_credits}"
            painter.setPen(QColor(self._color_text))
            text_rect = QRectF(0, 0, fixed_text_w, h)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text_str)
        
        # Icon position (fixed, based on fixed text width)
        icon_x = fixed_text_w + spacing
        icon_y = (h - icon_h) / 2
        
        # Define Thunderbolt Path (Classic ZigZag)
        path_points = [
            (0.65, 0.0),  # Top Right Start
            (0.10, 0.55), # Middle Left
            (0.45, 0.55), # Horizontal Inset Right
            (0.35, 1.0),  # Bottom Tip
            (0.90, 0.45), # Middle Right
            (0.55, 0.45), # Horizontal Inset Left
        ]
        
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        start_pt = path_points[0]
        path.moveTo(icon_x + start_pt[0] * icon_w, icon_y + start_pt[1] * icon_h)
        for pt in path_points[1:]:
            path.lineTo(icon_x + pt[0] * icon_w, icon_y + pt[1] * icon_h)
        path.closeSubpath()
        
        # Draw Empty Background
        painter.setPen(Qt.PenStyle.NoPen)
        empty_c = QColor(self._color_empty)
        
        # Adjust transparency for dark mode visibility
        # Check if color is dark (simple check)
        is_dark_bg = empty_c.lightness() < 128
        final_empty_alpha = self._empty_transparency
        
        if is_dark_bg:
            # Brighten it up significantly in dark mode
            # Use a minimum alpha of 0.6 if it was lower
            final_empty_alpha = max(0.6, self._empty_transparency)
            # Lift the brightness if it's too dark
            if empty_c.value() < 60:
                empty_c = empty_c.lighter(150)
        
        empty_c.setAlphaF(final_empty_alpha)
        painter.setBrush(QBrush(empty_c))
        painter.drawPath(path)
        
        # Draw Filled Portion (Clipped) with gradient
        if self._max_credits > 0:
            fill_ratio = self._current_credits / self._max_credits
        else:
            fill_ratio = 0.0
        fill_ratio = max(0.0, min(1.0, fill_ratio))
        
        # Calculate fill height
        fill_h = icon_h * fill_ratio
        fill_y = icon_y + icon_h - fill_h
        
        fill_rect = QRectF(icon_x, fill_y, icon_w, fill_h)
        
        # Flat color based on fill ratio with interpolation
        # 100% - 75%: Blue (Theme.accent_turbo)
        # 75% - 50%: Green (Theme.success)
        # 50% - 35%: Orange (Theme.warning)
        # 35% - 0%: Red (Theme.error)
        
        # Define stops
        stops = [
            (1.0, QColor("#2196F3")),   # Blue
            (0.75, QColor("#2196F3")),  # Blue (Stay blue until 75%)
            (0.50, QColor("#4CAF50")),  # Green
            (0.35, QColor("#FF9800")),  # Orange
            (0.15, QColor("#F44336")),  # Red
            (0.0, QColor("#F44336"))    # Red
        ]
        
        # Find segment
        c1 = stops[-1][1] # Default low
        c2 = stops[0][1] # Default high
        t = 0.0
        
        for i in range(len(stops) - 1):
            high_stop = stops[i]
            low_stop = stops[i+1]
            if fill_ratio <= high_stop[0] and fill_ratio >= low_stop[0]:
                c1 = low_stop[1]
                c2 = high_stop[1]
                # Calculate local t (0.0 to 1.0 within segment)
                range_span = high_stop[0] - low_stop[0]
                if range_span > 0:
                    t = (fill_ratio - low_stop[0]) / range_span
                else:
                    t = 0.0
                break
        
        # Interpolate
        r = c1.red() + (c2.red() - c1.red()) * t
        g = c1.green() + (c2.green() - c1.green()) * t
        b = c1.blue() + (c2.blue() - c1.blue()) * t
        
        final_color = QColor(int(r), int(g), int(b))
        
        # Apply gain/transparency
        h_v, s_v, v_v, _ = final_color.getHsvF()
        v_v = min(1.0, v_v * self._gain)
        final_color.setHsvF(h_v, s_v, v_v, self._filled_transparency)
        
        painter.setClipPath(path)
        painter.setBrush(QBrush(final_color))
        painter.drawRect(fill_rect)


