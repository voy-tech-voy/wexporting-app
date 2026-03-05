from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QObject

class AnimationDriver(QObject):
    """
    Manages animation easing curves and timing to avoid hardcoding.
    Wraps a QPropertyAnimation (or similar) and provides high-level control
    over easing types and parameters.
    """
    
    # Comprehensive mapping of string names to QEasingCurve types
    EASING_MAP = {
        "Linear": QEasingCurve.Type.Linear,
        "OutQuad": QEasingCurve.Type.OutQuad,
        "OutCubic": QEasingCurve.Type.OutCubic,
        "OutQuart": QEasingCurve.Type.OutQuart,
        "OutQuint": QEasingCurve.Type.OutQuint,
        "OutSine": QEasingCurve.Type.OutSine,
        "OutExpo": QEasingCurve.Type.OutExpo,
        "OutCirc": QEasingCurve.Type.OutCirc,
        "OutBack": QEasingCurve.Type.OutBack,
        "OutElastic": QEasingCurve.Type.OutElastic,
        "OutBounce": QEasingCurve.Type.OutBounce,
        
        "InQuad": QEasingCurve.Type.InQuad,
        "InCubic": QEasingCurve.Type.InCubic,
        "InQuart": QEasingCurve.Type.InQuart,
        "InQuint": QEasingCurve.Type.InQuint,
        "InSine": QEasingCurve.Type.InSine,
        "InExpo": QEasingCurve.Type.InExpo,
        "InCirc": QEasingCurve.Type.InCirc,
        "InBack": QEasingCurve.Type.InBack,
        "InElastic": QEasingCurve.Type.InElastic,
        "InBounce": QEasingCurve.Type.InBounce,
        
        "InOutQuad": QEasingCurve.Type.InOutQuad,
        "InOutCubic": QEasingCurve.Type.InOutCubic,
        "InOutQuart": QEasingCurve.Type.InOutQuart,
        "InOutQuint": QEasingCurve.Type.InOutQuint,
        "InOutSine": QEasingCurve.Type.InOutSine,
        "InOutExpo": QEasingCurve.Type.InOutExpo,
        "InOutCirc": QEasingCurve.Type.InOutCirc,
        "InOutBack": QEasingCurve.Type.InOutBack,
        "InOutElastic": QEasingCurve.Type.InOutElastic,
        "InOutBounce": QEasingCurve.Type.InOutBounce,
    }

    def __init__(self, animation: QPropertyAnimation, duration=300, easing="OutQuad"):
        super().__init__()
        self._animation = animation
        self._duration = duration
        self._easing_name = easing
        
        # Extended parameters for specific curves
        self._amplitude = 1.0  # For Elastic/Bounce
        self._period = 0.3     # For Elastic
        self._overshoot = 1.70158 # For Back (default Qt value)
        
        # Apply initial settings
        self.apply()

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, ms):
        self._duration = ms
        self._animation.setDuration(ms)

    @property
    def easing_type(self):
        """Name of the easing curve (for DevPanel inspection)."""
        return self._easing_name

    @easing_type.setter
    def easing_type(self, name):
        if name in self.EASING_MAP:
            self._easing_name = name
            self._update_curve()

    @property
    def amplitude(self):
        return self._amplitude

    @amplitude.setter
    def amplitude(self, value):
        self._amplitude = value
        self._update_curve()

    @property
    def period(self):
        return self._period

    @period.setter
    def period(self, value):
        self._period = value
        self._update_curve()

    @property
    def overshoot(self):
        return self._overshoot

    @overshoot.setter
    def overshoot(self, value):
        self._overshoot = value
        self._update_curve()

    def _update_curve(self):
        curve_type = self.EASING_MAP.get(self._easing_name, QEasingCurve.Type.OutQuad)
        curve = QEasingCurve(curve_type)
        
        # Apply specialized parameters where applicable
        # Note: Qt's QEasingCurve only uses these params for specific curve types,
        # but setting them is generally safe (ignored if not relevant).
        
        if "Elastic" in self._easing_name:
             if self._amplitude is not None: curve.setAmplitude(self._amplitude)
             if self._period is not None: curve.setPeriod(self._period)
             
        if "Back" in self._easing_name:
            if self._overshoot is not None: curve.setOvershoot(self._overshoot)
            
        if "Bounce" in self._easing_name:
            if self._amplitude is not None: curve.setAmplitude(self._amplitude)
            
        self._animation.setEasingCurve(curve)

    def apply(self):
        self._animation.setDuration(self._duration)
        self._update_curve()
        
    def start(self):
        self._animation.start()
        
    def stop(self):
        self._animation.stop()
        
    def setStartValue(self, val):
        self._animation.setStartValue(val)
        
    def setEndValue(self, val):
        self._animation.setEndValue(val)
        
    @property
    def state(self):
        return self._animation.state()

    @property
    def finished(self):
        return self._animation.finished
