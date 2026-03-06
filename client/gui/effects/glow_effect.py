from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QRectF, QObject, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QLinearGradient, QBrush, QPixmap, QImage, QPen
from PySide6.QtWidgets import QWidget, QGraphicsBlurEffect
import math
import colorsys
import random
import time
from enum import Enum
from abc import ABC, abstractmethod

class GlowState(Enum):
    IDLE = "idle"
    HOVER = "hover"  
    ACTIVE = "active"
    CLICKED = "clicked"


class GlowEffect(ABC):
    """
    Base class for modular glow effects.
    Subclass this to create new toggleable effects like ripple, pulse, shimmer, etc.
    """
    
    def __init__(self, config_source):
        """
        Args:
            config_source: Class containing configuration constants (e.g., SiriGlowOverlay)
        """
        self._config = config_source
        self._active = False
        self._start_time = 0
        self._enabled = True
        
    @property
    def is_active(self) -> bool:
        """Whether the effect is currently animating"""
        return self._active
    
    @property
    def enabled(self) -> bool:
        """Whether the effect is enabled (can be triggered)"""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        if not value:
            self._active = False
    
    def trigger(self):
        """Start the effect animation"""
        if self._enabled:
            self._active = True
            self._start_time = time.time()
            self._on_trigger()
    
    def _on_trigger(self):
        """Override for custom trigger behavior"""
        pass
    
    @abstractmethod
    def update(self) -> bool:
        """
        Update animation state. Called each frame.
        Returns: True if effect is still active, False if complete
        """
        pass
    
    @abstractmethod
    def paint(self, painter: QPainter, rect: QRect):
        """Render the effect"""
        pass


class RippleEffect(GlowEffect):
    """
    Expanding ring effect that emanates from center on hover/click.
    Creates an "energy burst" visual with configurable ring count and timing.
    """
    
    def __init__(self, config_source):
        super().__init__(config_source)
        self._ring_phases = []  # Progress of each ring (0.0 to 1.0)
        
    def _on_trigger(self):
        """Reset ring phases for new animation"""
        ring_count = getattr(self._config, 'RIPPLE_RING_COUNT', 2)
        self._ring_phases = [0.0] * ring_count
        
    def update(self) -> bool:
        """Update ring expansion progress"""
        if not self._active:
            return False
            
        elapsed_ms = (time.time() - self._start_time) * 1000
        duration = getattr(self._config, 'RIPPLE_DURATION_MS', 400)
        ring_delay = getattr(self._config, 'RIPPLE_RING_DELAY_MS', 80)
        
        all_complete = True
        for i in range(len(self._ring_phases)):
            ring_start = i * ring_delay
            ring_elapsed = elapsed_ms - ring_start
            
            if ring_elapsed < 0:
                self._ring_phases[i] = 0.0
                all_complete = False
            elif ring_elapsed >= duration:
                self._ring_phases[i] = 1.0
            else:
                # Apply ease-out curve
                linear = ring_elapsed / duration
                ease_power = getattr(self._config, 'RIPPLE_EASE_POWER', 1.5)
                self._ring_phases[i] = 1.0 - pow(1.0 - linear, ease_power)
                all_complete = False
        
        if all_complete:
            self._active = False
            
        return self._active
    
    def paint(self, painter: QPainter, rect: QRect):
        """Draw expanding rings"""
        if not self._active and all(p >= 1.0 for p in self._ring_phases):
            return
            
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x = rect.width() / 2
        center_y = rect.height() / 2
        max_radius = max(rect.width(), rect.height()) / 2
        max_scale = getattr(self._config, 'RIPPLE_MAX_SCALE', 1.3)
        
        thickness = getattr(self._config, 'RIPPLE_RING_THICKNESS', 8)
        max_opacity = getattr(self._config, 'RIPPLE_RING_OPACITY', 180)
        color = getattr(self._config, 'RIPPLE_RING_COLOR', (255, 255, 255))
        
        for phase in self._ring_phases:
            if phase <= 0.0:
                continue
                
            # Ring expands from 0 to max_radius * max_scale
            radius = phase * max_radius * max_scale
            
            # Opacity fades out as ring expands
            opacity = int(max_opacity * (1.0 - phase))
            
            if opacity <= 0:
                continue
                
            pen = QPen(QColor(color[0], color[1], color[2], opacity))
            pen.setWidth(thickness)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            painter.drawEllipse(
                int(center_x - radius),
                int(center_y - radius),
                int(radius * 2),
                int(radius * 2)
            )
        
        painter.restore()


class SiriGlowOverlay(QWidget):
    """
    Capsule-shaped glow widget with Siri-style gradient colors.
    Parented to top-level window to avoid clipping.
    Contains ALL configuration for both glow and noise effects.
    """
    
    # ========== GLOW EFFECT CONFIGURATION ==========
    # Adjust these parameters to tune the glow appearance
    
    # Hover Animation
    HOVER_FADE_IN_MS = 430              # Fade-in duration (ms) when hovering
    HOVER_FADE_OUT_MS = 478             # Fade-out duration (ms) when leaving
    HOVER_MAX_OPACITY = 1.00             # Max opacity when hovered (1.0 = full strength)
    
    # Interior Masking
    # Creates a soft hole in the center so glow only affects edges/outside.
    # MASK_PADDING should be kept in sync with GlowEffectManager.GLOW_PADDING
    # so the hole aligns with the actual button boundary.
    MASK_INTERIOR = True
    MASK_PADDING = 50                   # Matches GLOW_PADDING — aligns cutout with button edge
    MASK_FEATHER = 35                   # Gaussian blur radius for halo feathering
    MASK_CORNER_RADIUS = 36             # Corner softness to avoid boxy look
    
    # Blob appearance
    BLOB_RADIUS = 118                    # Size of each color blob
    BLOB_OPACITY_CENTER = 255           # Opacity at blob center (0-255) - MAX STRENGTH
    BLOB_OPACITY_MID = 255              # Opacity at blob mid-point (0-255) - STRONGER
    BLOB_OPACITY_EDGE = 0               # Opacity at blob edge (0-255)
    
    # Ellipse orbit
    ELLIPSE_SCALE_X = 0.62               # Horizontal ellipse size (0.0-1.0, fraction of overlay width)
    ELLIPSE_SCALE_Y = 0.16               # Vertical ellipse size (0.0-1.0, fraction of overlay height)
    
    # Pulsation
    PULSE_OPACITY_MIN = 0.24             # Minimum opacity during pulse (0.0-1.0)
    PULSE_OPACITY_MAX = 1.00             # Maximum opacity during pulse (0.0-1.0)
    
    # Color shifting
    HUE_SHIFT_DEGREES = 30              # Maximum hue shift in degrees (0-360)
    HUE_SHIFT_PHASE_START = 0.25        # Phase where shift starts fading (0.0-1.0)
    HUE_SHIFT_PHASE_END = 0.75          # Phase where shift starts rising (0.0-1.0)
    
    # Base colors (RGB tuples)
    COLOR_BLUE = (30, 144, 255)         # Dodger Blue
    COLOR_GREEN = (16, 185, 129)        # Emerald Green
    COLOR_ORANGE = (255, 165, 0)        # Orange
    
    # Blob positioning (phase offsets, 0.0-1.0)
    BLOB_PHASE_BLUE = 0.0               # Blue blob starting position
    BLOB_PHASE_GREEN = 0.333            # Green blob starting position (120° ahead)
    BLOB_PHASE_ORANGE = 0.667           # Orange blob starting position (240° ahead)
    
    # ========== ANTI-BANDING NOISE CONFIGURATION ==========
    # Noise overlay parameters (applied via separate GlowNoiseOverlay widget)
    # Prevents gradient banding artifacts with subtle film-grain texture
    
    # Master opacity of the noise layer (0-255)
    # Lower = more subtle, Higher = more visible grain
    # Recommended: 8-15 for subtle anti-banding, 20-40 for visible grain effect
    NOISE_OPACITY = 36
    
    # Size of the noise texture tile in pixels
    # Larger = more varied patterns, slightly more memory
    # Smaller = faster generation, may show visible tiling
    # Recommended: 64-128 pixels
    NOISE_TILE_SIZE = 64
    
    # Noise intensity range (-X to +X)
    # Controls the alpha range of individual noise pixels
    # Higher = stronger individual grain particles
    # Recommended: 20-40 for subtle effect, 80-150 for visible grain
    NOISE_INTENSITY = 25
    
    # Noise distribution bias (affects grain character)
    # True = bidirectional (white + black noise, more natural film grain)
    # False = unidirectional (white only, additive grain)
    NOISE_BIDIRECTIONAL = True
    
    # Edge fade settings - radial gradient mask to smooth out edges
    # Prevents visible "cut-off" at the noise boundary
    # EDGE_FADE_START: Where the fade begins (0.0 = center, 1.0 = edge)
    # Recommended: 0.5-0.7 for smooth fade, 0.9 for subtle fade
    NOISE_EDGE_FADE_START = 0.6
    
    # Debug visualization
    # Set to True to show yellow outline and visualize the radial gradient mask
    # Useful for tuning NOISE_EDGE_FADE_START and verifying coverage
    DEBUG_SHOW_NOISE_AREA = False
    
    # Set to True to visualize the ripple mask (white rings) at 70% opacity
    DEBUG_SHOW_RIPPLE_MASK = False
    
    # ========== RIPPLE ACTIVATION EFFECT ==========
    # Expanding ring effect that triggers on hover/click
    # Creates an "energy burst" emanating from the button center
    
    # Number of ripple rings (1-3 recommended)
    RIPPLE_RING_COUNT = 2
    
    # Ring appearance
    RIPPLE_RING_THICKNESS = 8           # Thickness of each ring in pixels
    RIPPLE_RING_OPACITY = 180           # Max opacity of rings (0-255)
    RIPPLE_RING_COLOR = (255, 255, 255) # Ring color (RGB tuple)
    
    # Animation timing
    RIPPLE_DURATION_MS = 400            # Total ripple animation duration
    RIPPLE_RING_DELAY_MS = 80           # Delay between successive rings
    
    # Animation curve (0.0 = linear, higher = more acceleration at start)
    # Controls how "weighted/fast" the expansion feels
    # 0.5 = subtle ease-out, 1.0 = moderate, 2.0 = very snappy start
    RIPPLE_EASE_POWER = 1.5
    
    # Scale: how far the ripple expands (1.0 = to edge, 1.5 = 50% beyond)
    RIPPLE_MAX_SCALE = 1.3
    
    # ===============================================
    
    def __init__(self, parent=None, scale_factor=1.0, ellipse_x=None, ellipse_y=None):
        super().__init__(parent)
        self.scale_factor = scale_factor
        self.ellipse_x = ellipse_x if ellipse_x is not None else self.ELLIPSE_SCALE_X
        self.ellipse_y = ellipse_y if ellipse_y is not None else self.ELLIPSE_SCALE_Y
        
        self._pulse_phase = 0.0  # 0.0 to 1.0 for pulse cycle
        self._ripple_phases = []  # Ring phases for ripple mask (0.0 to 1.0 each)
        self._ripple_active = False
        self._master_opacity = 0.0  # Start invisible
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._cached_mask = None
        self._cached_size = None

    def get_master_opacity(self):
        return self._master_opacity
        
    def set_master_opacity(self, opacity):
        self._master_opacity = opacity
        self.update()
        
    masterOpacity = Property(float, get_master_opacity, set_master_opacity)
        
    def set_pulse_phase(self, phase):
        """Set the current pulse phase (0.0-1.0)"""
        self._pulse_phase = phase
        self.update()
        
    def set_ripple_phases(self, phases: list, active: bool):
        """Set ripple ring phases for mask generation"""
        self._ripple_phases = phases
        self._ripple_active = active
        
    def _generate_ripple_mask(self, w, h) -> QPixmap:
        """Generate a mask where expanding rings reveal the glow"""
        mask = QPixmap(w, h)
        mask.fill(Qt.GlobalColor.black)  # Start with black (hide all)
        
        if not self._ripple_phases:
            return mask
            
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_x = w / 2
        center_y = h / 2
        max_radius = max(w, h) / 2
        max_scale = self.RIPPLE_MAX_SCALE
        thickness = self.RIPPLE_RING_THICKNESS
        
        for phase in self._ripple_phases:
            if phase <= 0.0:
                continue
                
            # Ring radius expands from 0 to max
            radius = phase * max_radius * max_scale
            
            # Ring opacity (white = reveal) - fades as it expands
            opacity = int(255 * (1.0 - phase * phase))
            
            if opacity <= 0:
                continue
            
            # Draw white ring (reveals glow underneath)
            pen = QPen(QColor(255, 255, 255, opacity))
            pen.setWidth(int(thickness * (1.0 + phase)))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            painter.drawEllipse(
                int(center_x - radius),
                int(center_y - radius),
                int(radius * 2),
                int(radius * 2)
            )
            
            # Add filled center that stays revealed
            if phase > 0.3:
                fill_radius = radius * 0.3
                fill_opacity = int(200 * min(1.0, (phase - 0.3) / 0.4))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, fill_opacity))
                painter.drawEllipse(
                    int(center_x - fill_radius),
                    int(center_y - fill_radius),
                    int(fill_radius * 2),
                    int(fill_radius * 2)
                )
        
        painter.end()
        return mask
        
    def _get_mask_cache_key(self):
        return (self.width(), self.height(), self.MASK_PADDING, self.MASK_FEATHER, self.MASK_CORNER_RADIUS)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._cached_mask = None  # Invalidate — will be rebuilt on next paint

    def _generate_feathered_mask(self, w, h) -> QPixmap:
        """
        Generates a true-Gaussian feathered halo mask.
        A 'doughnut' ring is drawn and blurred. Then, a perimeter fade (vignette)
        is explicitly multiplied against it to guarantee the alpha reaches 0 perfectly
        at the widget bounds, preventing ANY hard cuts/geometric bounding boxes.
        """
        pad = int(self.MASK_PADDING * self.scale_factor)
        cr  = int(self.MASK_CORNER_RADIUS * self.scale_factor)
        f   = int(self.MASK_FEATHER * self.scale_factor)

        # The mask's physical bounds before blurring
        outer_pad = pad - int(30 * self.scale_factor)   # ring extends 30px outside button edge
        inner_pad = pad + int(4 * self.scale_factor)    # ring extends 4px inside button edge

        # Guard: degenerate geometry
        if outer_pad < 0 or inner_pad <= 0 or (w - 2*inner_pad) <= 0 or (h - 2*inner_pad) <= 0:
            full_mask = QPixmap(w, h)
            full_mask.fill(Qt.GlobalColor.white)
            return full_mask

        # 1. Base doughnut shape
        raw_mask = QPixmap(w, h)
        raw_mask.fill(Qt.GlobalColor.transparent)
        p = QPainter(raw_mask)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        from PySide6.QtGui import QPainterPath, QLinearGradient
        from PySide6.QtCore import QPointF
        
        outer_path = QPainterPath()
        outer_path.addRoundedRect(outer_pad, outer_pad, w - 2*outer_pad, h - 2*outer_pad, cr + 10, cr + 10)

        inner_path = QPainterPath()
        inner_path.addRoundedRect(inner_pad, inner_pad, w - 2*inner_pad, h - 2*inner_pad, max(0, cr - 2), max(0, cr - 2))

        doughnut = outer_path.subtracted(inner_path)
        p.setBrush(Qt.GlobalColor.white)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(doughnut)
        p.end()

        # No blur scenario (should be rare)
        if f <= 0:
            return raw_mask

        # 2. Apply true Gaussian blur via scene
        from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
        scene = QGraphicsScene()
        scene.setSceneRect(0, 0, w, h)
        item = QGraphicsPixmapItem(raw_mask)
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(f)
        item.setGraphicsEffect(blur)
        scene.addItem(item)

        blurred_mask = QPixmap(w, h)
        blurred_mask.fill(Qt.GlobalColor.transparent)
        bp = QPainter(blurred_mask)
        scene.render(bp, target=QRectF(0, 0, w, h), source=QRectF(0, 0, w, h))
        bp.end()
        
        # 3. Apply perimeter fade (soft vignette limit) to prevent edge clipping
        # Define the zone where the fade happens on the outer boundaries.
        fade_thickness = max(5, int(15 * self.scale_factor))  # Pixels from edge to start fading to absolute 0
        
        vignette_mask = QPixmap(w, h)
        vignette_mask.fill(Qt.GlobalColor.transparent)
        vp = QPainter(vignette_mask)
        vp.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw a rounded rect that fades at its edges using a stroked path with a gradient,
        # or simpler: a solid white rect with inner fading.
        vp.setBrush(Qt.GlobalColor.white)
        vp.setPen(Qt.PenStyle.NoPen)
        
        # We want to draw a shape that is solid white in the middle but fades to transparent
        # at the exact edges of the (w, h) pixmap.
        # We can do this efficiently by drawing 4 linear gradients for the borders
        # onto a fully white center.
        
        # Center solid area
        vp.drawRect(fade_thickness, fade_thickness, w - 2*fade_thickness, h - 2*fade_thickness)
        
        # Left edge fade
        left_grad = QLinearGradient(0, 0, fade_thickness, 0)
        left_grad.setColorAt(0, Qt.GlobalColor.transparent)
        left_grad.setColorAt(1, Qt.GlobalColor.white)
        vp.fillRect(0, fade_thickness, fade_thickness, h - 2*fade_thickness, left_grad)
        
        # Right edge fade
        right_grad = QLinearGradient(w, 0, w - fade_thickness, 0)
        right_grad.setColorAt(0, Qt.GlobalColor.transparent)
        right_grad.setColorAt(1, Qt.GlobalColor.white)
        vp.fillRect(w - fade_thickness, fade_thickness, fade_thickness, h - 2*fade_thickness, right_grad)
        
        # Top edge fade
        top_grad = QLinearGradient(0, 0, 0, fade_thickness)
        top_grad.setColorAt(0, Qt.GlobalColor.transparent)
        top_grad.setColorAt(1, Qt.GlobalColor.white)
        vp.fillRect(fade_thickness, 0, w - 2*fade_thickness, fade_thickness, top_grad)
        
        # Bottom edge fade
        bot_grad = QLinearGradient(0, h, 0, h - fade_thickness)
        bot_grad.setColorAt(0, Qt.GlobalColor.transparent)
        bot_grad.setColorAt(1, Qt.GlobalColor.white)
        vp.fillRect(fade_thickness, h - fade_thickness, w - 2*fade_thickness, fade_thickness, bot_grad)
        
        # Corners (radial gradients to marry the edges smoothly)
        def draw_corner(cx, cy, radius, start_angle):
            grad = QRadialGradient(cx, cy, radius)
            grad.setColorAt(0, Qt.GlobalColor.white)
            grad.setColorAt(1, Qt.GlobalColor.transparent)
            vp.setBrush(grad)
            vp.drawPie(int(cx - radius), int(cy - radius), int(radius*2), int(radius*2), int(start_angle * 16), int(90 * 16))

        # Top-Left corner (cx=fade_thickness, cy=fade_thickness, draw pie 90->180)
        draw_corner(fade_thickness, fade_thickness, fade_thickness, 90)
        # Top-Right corner
        draw_corner(w - fade_thickness, fade_thickness, fade_thickness, 0)
        # Bottom-Right corner
        draw_corner(w - fade_thickness, h - fade_thickness, fade_thickness, 270)
        # Bottom-Left corner
        draw_corner(fade_thickness, h - fade_thickness, fade_thickness, 180)
        
        vp.end()
        
        # 4. Multiply the blurred mask by the vignette
        final_bp = QPainter(blurred_mask)
        final_bp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        final_bp.drawPixmap(0, 0, vignette_mask)
        final_bp.end()
        
        return blurred_mask

    def paintEvent(self, event):
        w = self.width()
        h = self.height()

        # ── Step 1: Render glow blobs ──────────────────────────────────────
        # The widget is already oversized by GLOW_PADDING (50px) on each side,
        # so blobs orbit the widget centre and fade to alpha=0 well within
        # the widget bounds. No canvas padding / negative-offset tricks needed.
        glow_pixmap = QPixmap(w, h)
        glow_pixmap.fill(Qt.GlobalColor.transparent)

        glow_painter = QPainter(glow_pixmap)
        glow_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        phase = self._pulse_phase

        # Hue shift
        if phase < self.HUE_SHIFT_PHASE_START:
            shift_strength = 1.0 - (phase / self.HUE_SHIFT_PHASE_START)
        elif phase > self.HUE_SHIFT_PHASE_END:
            shift_strength = (phase - self.HUE_SHIFT_PHASE_END) / (1.0 - self.HUE_SHIFT_PHASE_END)
        else:
            shift_strength = 0.0

        hue_shift = (self.HUE_SHIFT_DEGREES * shift_strength) / 360.0

        def shift_hue(rgb, shift):
            r, g, b = rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0
            h_val, s, v = colorsys.rgb_to_hsv(r, g, b)
            h_val = (h_val + shift) % 1.0
            r, g, b = colorsys.hsv_to_rgb(h_val, s, v)
            return (int(r * 255), int(g * 255), int(b * 255))

        blue   = shift_hue(self.COLOR_BLUE,   hue_shift)
        green  = shift_hue(self.COLOR_GREEN,  hue_shift)
        orange = shift_hue(self.COLOR_ORANGE, hue_shift)

        pulse_range   = self.PULSE_OPACITY_MAX - self.PULSE_OPACITY_MIN
        pulse_opacity = self.PULSE_OPACITY_MIN + pulse_range * (0.5 + 0.5 * math.sin(phase * 2 * math.pi))
        glow_painter.setOpacity(pulse_opacity)

        center_x = w / 2
        center_y = h / 2
        min_dim   = min(w, h)
        orbit_rx  = (min_dim / 2) * self.ellipse_x
        orbit_ry  = (min_dim / 2) * self.ellipse_y
        blob_radius = int(self.BLOB_RADIUS * self.scale_factor)

        blobs = [
            {'color': blue,   'phase_offset': self.BLOB_PHASE_BLUE},
            {'color': green,  'phase_offset': self.BLOB_PHASE_GREEN},
            {'color': orange, 'phase_offset': self.BLOB_PHASE_ORANGE},
        ]
        glow_painter.setPen(Qt.PenStyle.NoPen)

        for blob in blobs:
            angle  = (phase + blob['phase_offset']) * 2 * math.pi
            bx     = center_x + orbit_rx * math.cos(angle)
            by     = center_y + orbit_ry * math.sin(angle)
            grad   = QRadialGradient(bx, by, blob_radius)
            c      = blob['color']
            grad.setColorAt(0.0, QColor(c[0], c[1], c[2], self.BLOB_OPACITY_CENTER))
            grad.setColorAt(0.5, QColor(c[0], c[1], c[2], self.BLOB_OPACITY_MID))
            grad.setColorAt(1.0, QColor(c[0], c[1], c[2], self.BLOB_OPACITY_EDGE))
            glow_painter.setBrush(QBrush(grad))
            glow_painter.drawEllipse(
                int(bx - blob_radius), int(by - blob_radius),
                blob_radius * 2,       blob_radius * 2
            )

        glow_painter.end()

        # ── Step 2: Ripple layer (optional) ───────────────────────────────
        final_pixmap = QPixmap(w, h)
        final_pixmap.fill(Qt.GlobalColor.transparent)
        final_painter = QPainter(final_pixmap)
        final_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        final_painter.drawPixmap(0, 0, glow_pixmap)

        if self._ripple_active and self._ripple_phases:
            mask = self._generate_ripple_mask(w, h)

            masked_glow = QPixmap(w, h)
            masked_glow.fill(Qt.GlobalColor.transparent)
            masked_painter = QPainter(masked_glow)
            masked_painter.drawPixmap(0, 0, glow_pixmap)
            masked_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            mask_rgb = QPixmap(w, h)
            mask_rgb.fill(Qt.GlobalColor.white)
            mask_rgb_p = QPainter(mask_rgb)
            mask_rgb_p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            mask_rgb_p.drawPixmap(0, 0, mask)
            mask_rgb_p.end()
            masked_painter.drawPixmap(0, 0, mask_rgb)
            masked_painter.end()

            final_painter.setOpacity(1.5)
            final_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            final_painter.drawPixmap(0, 0, masked_glow)
            final_painter.setOpacity(1.0)
            final_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # ── Step 3: Perfectly Feathered Window Mask ───────────────────────
        # Use our pre-cached true Gaussian blurred halo as an alpha window
        # (DestinationIn). This smoothly fades the glow out on the outer edge
        # (preventing clip) and smoothly fades it out towards the inner center.
        if self.MASK_INTERIOR and self.MASK_PADDING > 0:
            # Rebuild cache if params or size changed
            cache_key = self._get_mask_cache_key()
            if self._cached_mask is None or self._cached_size != cache_key:
                self._cached_mask = self._generate_feathered_mask(w, h)
                self._cached_size = cache_key

            final_painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_DestinationIn
            )
            final_painter.drawPixmap(0, 0, self._cached_mask)
            final_painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )

        final_painter.end()

        # ── Composite with master (hover-fade) opacity ────────────────────
        painter = QPainter(self)
        painter.setOpacity(self._master_opacity)
        painter.drawPixmap(0, 0, final_pixmap)

        # DEBUG: ripple rings
        if self.DEBUG_SHOW_RIPPLE_MASK and self._ripple_active and self._ripple_phases:
            painter.setOpacity(0.7)
            c_x = w / 2
            c_y = h / 2
            max_r = max(w, h) / 2
            for ph in self._ripple_phases:
                if ph <= 0.0:
                    continue
                r   = ph * max_r * self.RIPPLE_MAX_SCALE
                opc = int(255 * (1.0 - ph * ph))
                if opc <= 0:
                    continue
                pen = QPen(QColor(0, 255, 255, opc))
                pen.setWidth(int(self.RIPPLE_RING_THICKNESS * (1.0 + ph)))
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(int(c_x - r), int(c_y - r), int(r*2), int(r*2))
            painter.setOpacity(1.0)

class GlowNoiseOverlay(QWidget):
    """
    Anti-Banding Noise Overlay for Glow Effects
    ============================================
    
    Renders a subtle film-grain noise texture on top of blurred glow effects
    to prevent gradient banding artifacts. This overlay sits ABOVE the blurred
    glow widget and is NOT affected by the blur effect, ensuring crisp noise.
    
    Configuration:
    - All noise parameters are defined in SiriGlowOverlay class constants
    - This keeps all glow-related configuration in one place
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Generate static noise texture once (zero per-frame cost)
        self._noise_pixmap = self._generate_noise_texture()
        
    def _generate_noise_texture(self):
        """
        Generate a static noise texture to prevent gradient banding.
        Uses parameters from SiriGlowOverlay class constants.
        """
        size = SiriGlowOverlay.NOISE_TILE_SIZE
        intensity = SiriGlowOverlay.NOISE_INTENSITY
        bidirectional = SiriGlowOverlay.NOISE_BIDIRECTIONAL
        
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        
        # Generate noise pixels
        for y in range(size):
            for x in range(size):
                if bidirectional:
                    # Bidirectional: random value from -intensity to +intensity
                    # Positive = white pixel, Negative = black pixel
                    noise_val = random.randint(-intensity, intensity)
                    if noise_val > 0:
                        image.setPixelColor(x, y, QColor(255, 255, 255, noise_val))
                    elif noise_val < 0:
                        image.setPixelColor(x, y, QColor(0, 0, 0, abs(noise_val)))
                else:
                    # Unidirectional: white-only additive noise
                    alpha = random.randint(0, intensity)
                    if alpha > 0:
                        image.setPixelColor(x, y, QColor(255, 255, 255, alpha))
        
        return QPixmap.fromImage(image)
    
    def paintEvent(self, event):
        """
        Render the tiled noise texture with radial edge fade.
        Uses a radial gradient mask to smoothly fade out the noise at edges.
        """
        
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Step 1: Draw noise to a temporary pixmap
        noise_pixmap = QPixmap(w, h)
        noise_pixmap.fill(Qt.GlobalColor.transparent)
        noise_painter = QPainter(noise_pixmap)
        noise_painter.setOpacity(SiriGlowOverlay.NOISE_OPACITY / 255.0)
        noise_painter.drawTiledPixmap(noise_pixmap.rect(), self._noise_pixmap)
        noise_painter.end()
        
        # Step 2: Create radial gradient mask
        center_x = w / 2
        center_y = h / 2
        radius = max(w, h) / 2
        
        gradient = QRadialGradient(center_x, center_y, radius)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 255))
        gradient.setColorAt(SiriGlowOverlay.NOISE_EDGE_FADE_START, QColor(255, 255, 255, 255))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        
        # Step 3: Apply mask using composition
        mask_pixmap = QPixmap(w, h)
        mask_pixmap.fill(Qt.GlobalColor.transparent)
        mask_painter = QPainter(mask_pixmap)
        mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        mask_painter.setBrush(QBrush(gradient))
        mask_painter.setPen(Qt.PenStyle.NoPen)
        mask_painter.drawRect(0, 0, w, h)
        mask_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        mask_painter.drawPixmap(0, 0, noise_pixmap)
        mask_painter.end()
        
        # Draw the final masked noise to the widget
        painter.drawPixmap(0, 0, mask_pixmap)
        
        # DEBUG: Visualize the noise area and gradient mask
        if SiriGlowOverlay.DEBUG_SHOW_NOISE_AREA:
            # 1. Draw yellow outline around noise area boundary
            painter.setPen(QPen(QColor(255, 255, 0, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(0, 0, w, h)
            
            # 2. Visualize the radial gradient mask at 50% opacity
            mask_visual = QPixmap(w, h)
            mask_visual.fill(Qt.GlobalColor.transparent)
            mask_visual_painter = QPainter(mask_visual)
            mask_visual_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            mask_visual_painter.setBrush(QBrush(gradient))
            mask_visual_painter.setPen(Qt.PenStyle.NoPen)
            mask_visual_painter.drawRect(0, 0, w, h)
            mask_visual_painter.end()
            
            painter.setOpacity(0.5)
            painter.drawPixmap(0, 0, mask_visual)
            painter.setOpacity(1.0)

class RippleOverlay(QWidget):
    """
    Widget that hosts ripple effect rendering.
    Parented to top-level window to avoid clipping.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._ripple_effect = RippleEffect(SiriGlowOverlay)
        
    def trigger(self):
        """Start the ripple animation"""
        self._ripple_effect.trigger()
        
    def update_animation(self) -> bool:
        """Update and repaint. Returns True if still animating."""
        if self._ripple_effect.update():
            self.update()
            return True
        return False
        
    @property
    def is_active(self) -> bool:
        return self._ripple_effect.is_active
        
    def paintEvent(self, event):
        painter = QPainter(self)
        self._ripple_effect.paint(painter, self.rect())


class GlowEffectManager(QObject):
    """
    Manager for the Siri Glow effect and modular effects system.
    Handles lifecycle, positioning, state transitions, and optional effects like ripple.
    """
    
    # Master toggles for optional effects
    ENABLE_RIPPLE_EFFECT = False
    
    def __init__(self, parent_widget, top_level_window, scale_factor=1.0, ellipse_scale_x=None, ellipse_scale_y=None):
        super().__init__(parent_widget)
        self._widget = parent_widget
        self._top_window = top_level_window
        
        self._scale_factor = scale_factor
        self._ellipse_x = ellipse_scale_x
        self._ellipse_y = ellipse_scale_y
        
        # Core components
        self._glow_overlay = None
        self._noise_overlay = None
        self._pulse_timer = None
        self._pulse_start_time = 0
        
        # Modular effects registry
        self._effects = {}  # name -> overlay widget
        
        # Configuration
        self.GLOW_RADIUS = int(55 * self._scale_factor)
        self.GLOW_PADDING = int(50 * self._scale_factor)  # Scaled padding
        self.NOISE_AREA_SCALE = 1.35
        self.PULSE_DURATION_MS = 4000
        
        # State
        self._state = GlowState.IDLE
        self._dev_panel = None
        
        # Initialize
        self._setup_glow()
        self._setup_effects()
        
    def toggle_dev_panel(self):
        """Toggle the dev panel for live parameter tuning"""
        if self._dev_panel is None:
            from client.gui.effects.dev_panel import GlowDevPanel
            self._dev_panel = GlowDevPanel.create_for_glow(
                self._glow_overlay,
                self
            )
        
        if self._dev_panel.isVisible():
            self._dev_panel.hide()
        else:
            self._dev_panel.show()
            self._dev_panel.raise_()
        
    def _setup_glow(self):
        """Create the glow and noise overlays"""
        if self._top_window is None:
            return
            
        # Create glow overlay.
        # NOTE: We no longer use QGraphicsBlurEffect here — it clips to the
        # widget bounding rect in PySide6, producing a hard rectangular box.
        # Blur is now performed in software inside SiriGlowOverlay.paintEvent.
        self._glow_overlay = SiriGlowOverlay(
            self._top_window, 
            scale_factor=self._scale_factor,
            ellipse_x=self._ellipse_x,
            ellipse_y=self._ellipse_y
        )
        
        # Create noise overlay
        self._noise_overlay = GlowNoiseOverlay(self._top_window)
        
        # Position and show (initially hidden for IDLE state)
        self.update_position()
        self._glow_overlay.hide()
        self._noise_overlay.hide()
        
        # Start pulse timer
        self._pulse_start_time = time.time()
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_frame)
        self._pulse_timer.start(16)  # ~60 FPS
        
        # Opacity Animation
        self._opacity_anim = QPropertyAnimation(self._glow_overlay, b"masterOpacity")
        self._opacity_anim.setDuration(SiriGlowOverlay.HOVER_FADE_IN_MS)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._opacity_anim.finished.connect(self._on_anim_finished)

    # Easing Properties
    @Property(str)
    def animationEasing(self):
        return getattr(self, '_easing_style_name', 'InOutQuad')
        
    @animationEasing.setter
    def animationEasing(self, name):
        self._easing_style_name = name
        self._update_easing()

    @Property(float)
    def easingAmplitude(self):
        return getattr(self, '_easing_amp', 1.0)

    @easingAmplitude.setter
    def easingAmplitude(self, val):
        self._easing_amp = val
        self._update_easing()

    @Property(float)
    def easingPeriod(self):
        return getattr(self, '_easing_period', 0.3)

    @easingPeriod.setter
    def easingPeriod(self, val):
        self._easing_period = val
        self._update_easing()

    def _update_easing(self):
        name = getattr(self, '_easing_style_name', 'InOutQuad')
        amp = getattr(self, '_easing_amp', 1.0)
        period = getattr(self, '_easing_period', 0.3)
        
        try:
            curve_type = getattr(QEasingCurve.Type, name)
            easing = QEasingCurve(curve_type)
            easing.setOvershoot(amp)
            easing.setAmplitude(amp)
            easing.setPeriod(period)
            if hasattr(self, '_opacity_anim'):
                self._opacity_anim.setEasingCurve(easing)
        except:
            pass

    def _on_anim_finished(self):
        if self._state == GlowState.IDLE:
            self.hide()
        

            
    def _setup_effects(self):
        # ... (unchanged)
        """Initialize modular effects based on toggles"""
        if self._top_window is None:
            return
            
        # Ripple effect
        if self.ENABLE_RIPPLE_EFFECT:
            ripple = RippleOverlay(self._top_window)
            ripple.hide()
            self._effects['ripple'] = ripple
            
    def enable_effect(self, name: str, enabled: bool = True):
        """Enable or disable a named effect"""
        if name in self._effects:
            if not enabled:
                self._effects[name].hide()
                
    def trigger_effect(self, name: str):
        """Trigger a named effect animation"""
        if name in self._effects:
            effect = self._effects[name]
            effect.show()
            effect.raise_()
            self.update_position()  # Ensure correct position
            effect.trigger()
            
    def update_position(self):
        """Update overlay positions to match parent widget"""
        if not self._widget or not self._top_window:
            return
            
        # Use global coordinates for robust mapping
        global_pos = self._widget.mapToGlobal(QPoint(0, 0))
        btn_pos = self._top_window.mapFromGlobal(global_pos)
    
        w = self._widget.width()
        h = self._widget.height()
        
        # Glow position
        if self._glow_overlay:
            glow_rect = (
                btn_pos.x() - self.GLOW_PADDING,
                btn_pos.y() - self.GLOW_PADDING,
                w + (self.GLOW_PADDING * 2),
                h + (self.GLOW_PADDING * 2)
            )
            self._glow_overlay.setGeometry(*glow_rect)
        
        # Noise position (scaled larger)
        if self._noise_overlay:
            base_padding = self.GLOW_PADDING + self.GLOW_RADIUS
            visual_padding = int(base_padding * self.NOISE_AREA_SCALE)
            noise_rect = (
                btn_pos.x() - visual_padding,
                btn_pos.y() - visual_padding,
                w + (visual_padding * 2),
                h + (visual_padding * 2)
            )
            self._noise_overlay.setGeometry(*noise_rect)
            
        # Effects overlays (same as noise for full coverage)
        for effect in self._effects.values():
            base_padding = self.GLOW_PADDING + self.GLOW_RADIUS
            visual_padding = int(base_padding * self.NOISE_AREA_SCALE)
            effect_rect = (
                btn_pos.x() - visual_padding,
                btn_pos.y() - visual_padding,
                w + (visual_padding * 2),
                h + (visual_padding * 2)
            )
            effect.setGeometry(*effect_rect)
            
    def _update_frame(self):
        """Update all animations each frame"""
        # Continuously update position to track parent movements/resizes
        # This handles cases where the button's parent moves (e.g. sidebar slide)
        # but the button's local position doesn't change
        self.update_position()
        
        # Update pulse
        if self._glow_overlay:
            elapsed = time.time() - self._pulse_start_time
            phase = (elapsed * 1000 / self.PULSE_DURATION_MS) % 1.0
            self._glow_overlay.set_pulse_phase(phase)
            
        # Update ripple effect and pass phases to glow overlay
        if 'ripple' in self._effects and self._glow_overlay:
            ripple = self._effects['ripple']
            if hasattr(ripple, '_ripple_effect'):
                ripple_effect = ripple._ripple_effect
                ripple_effect.update()
                self._glow_overlay.set_ripple_phases(
                    ripple_effect._ring_phases.copy() if ripple_effect._ring_phases else [],
                    ripple_effect.is_active
                )
                if not ripple_effect.is_active:
                    ripple.hide()
            
        # Update other modular effects
        for name, effect in self._effects.items():
            if name == 'ripple':
                continue  # Already handled above
            if hasattr(effect, 'update_animation'):
                if not effect.update_animation() and not effect.is_active:
                    effect.hide()
        
    def hide(self):
        if self._glow_overlay: self._glow_overlay.hide()
        if self._noise_overlay: self._noise_overlay.hide()
        
    def show(self):
        if self._glow_overlay: self._glow_overlay.show()
        if self._noise_overlay: self._noise_overlay.show()

    def cleanup(self):
        if self._pulse_timer: self._pulse_timer.stop()
        if hasattr(self, '_opacity_anim'): self._opacity_anim.stop()
        if self._glow_overlay: self._glow_overlay.deleteLater()
        if self._noise_overlay: self._noise_overlay.deleteLater()
        for effect in self._effects.values():
            effect.deleteLater()
        
    def set_state(self, state: GlowState):
        """Set the current interaction state and trigger animations"""
        if self._state == state:
            return
            
        old_state = self._state
        self._state = state
        
        # State transition behaviors
        if state == GlowState.IDLE:
            # Fade out
            self._opacity_anim.stop()
            self._opacity_anim.setDuration(self._glow_overlay.HOVER_FADE_OUT_MS)
            self._opacity_anim.setStartValue(self._glow_overlay.masterOpacity)
            self._opacity_anim.setEndValue(0.0)
            self._opacity_anim.start()
            
        elif state == GlowState.HOVER:
            # Show and fade in
            if old_state == GlowState.IDLE:
                self.show()
                self._opacity_anim.stop()
                self._opacity_anim.setDuration(self._glow_overlay.HOVER_FADE_IN_MS)
                self._opacity_anim.setStartValue(self._glow_overlay.masterOpacity)
                self._opacity_anim.setEndValue(self._glow_overlay.HOVER_MAX_OPACITY)
                self._opacity_anim.start()
                self.trigger_effect('ripple')
            elif old_state == GlowState.CLICKED:
                # Return from clicked
                self._opacity_anim.stop()
                self._opacity_anim.setDuration(self._glow_overlay.HOVER_FADE_IN_MS)
                self._opacity_anim.setStartValue(self._glow_overlay.masterOpacity)
                self._opacity_anim.setEndValue(self._glow_overlay.HOVER_MAX_OPACITY)
                self._opacity_anim.start()
                
        elif state == GlowState.CLICKED:
            # Flash to full on click
            self._opacity_anim.stop()
            self._opacity_anim.setDuration(50)  # Quick flash
            self._opacity_anim.setStartValue(self._glow_overlay.masterOpacity)
            self._opacity_anim.setEndValue(1.0)
            self._opacity_anim.start()
            
            self.trigger_effect('ripple')
            QTimer.singleShot(150, lambda: self.set_state(GlowState.HOVER))
        
    def get_state(self) -> GlowState:
        """Get the current interaction state"""
        return self._state

