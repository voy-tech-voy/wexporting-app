"""
Status Panel Component - Mediator-Shell Architecture

Progress bars and status display for conversion operations.
Extracted from MainWindow to follow the Mediator-Shell pattern.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStatusBar
from PySide6.QtGui import QPainter, QLinearGradient, QColor
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property


class CustomProgressBar(QWidget):
    """
    Custom gradient progress bar with smooth animation.
    
    Features:
    - Animated progress transitions
    - Gradient fill with glow effect
    - Configurable color and height
    """
    
    def __init__(self, color: QColor, height: int = 4, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.progress = 0.0  # 0.0 to 1.0
        self.color = color
        self._animation = None
    
    def set_progress(self, value: float, animate: bool = True, min_duration_ms: int = 250):
        """
        Set progress value with optional animation.
        
        Args:
            value: Progress value (0.0 to 1.0)
            animate: Whether to animate the transition
            min_duration_ms: Minimum animation duration
        """
        target_value = max(0.0, min(1.0, value))
        
        # If not animating, set immediately
        if not animate:
            if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
                self._animation.stop()
            self.progress = target_value
            self.repaint()
            return
        
        # If new file started (target < current), reset immediately without animation
        if target_value < self.progress - 0.1:
            if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
                self._animation.stop()
            self.progress = target_value
            self.repaint()
            return
        
        # Stop current animation if running
        if self._animation and self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.stop()
        
        # Calculate animation duration based on progress distance
        distance = abs(target_value - self.progress)
        duration = max(min_duration_ms, int(distance * 500))
        
        # Create smooth animation from current position
        self._animation = QPropertyAnimation(self, b"progress_value")
        self._animation.setDuration(duration)
        self._animation.setStartValue(self.progress)
        self._animation.setEndValue(target_value)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.start()
    
    @Property(float)
    def progress_value(self) -> float:
        return self.progress
    
    @progress_value.setter
    def progress_value(self, value: float):
        self.progress = value
        self.repaint()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = self.rect()
        
        # Background (dark)
        painter.fillRect(rect, QColor(60, 60, 60, 80))
        
        width = int(rect.width() * self.progress)
        # Ensure at least 1px visible if > 0
        if self.progress > 0 and width == 0:
            width = 1
        
        if width > 0:
            gradient = QLinearGradient(0, 0, width, 0)
            gradient.setColorAt(0, self.color)
            gradient.setColorAt(1, self.color.lighter(130))
            painter.fillRect(0, 0, width, rect.height(), gradient)
        
        painter.end()


class StatusPanel(QWidget):
    """
    Status panel with dual progress bars (file + total).
    
    Features:
    - Single file progress bar (blue, top)
    - Total progress bar (green, bottom)
    - Status text updates
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setObjectName("StatusPanel")
        self._completed_files_count = 0
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the status panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        
        # Single File Progress (Blue, Top)
        self.file_progress_bar = CustomProgressBar(QColor(33, 150, 243), height=3)
        
        # Total Progress (Green, Bottom)
        self.total_progress_bar = CustomProgressBar(QColor(76, 175, 80), height=3)
        
        layout.addWidget(self.file_progress_bar)
        layout.addWidget(self.total_progress_bar)
    
    # --- Public API for Mediator ---
    
    def set_file_progress(self, value: float):
        """Set single file progress (0.0 to 1.0)."""
        self.file_progress_bar.set_progress(value)
    
    def set_total_progress(self, value: float):
        """Set total progress (0.0 to 1.0)."""
        self.total_progress_bar.set_progress(value)
    
    def update_progress(self, file_progress: float, total_files: int):
        """
        Update progress based on file completion.
        
        Args:
            file_progress: Progress of current file (0.0 to 1.0)
            total_files: Total number of files
        """
        self.file_progress_bar.set_progress(file_progress)
        
        if total_files > 0:
            base_progress = self._completed_files_count / total_files
            current_fraction = file_progress / total_files
            self.total_progress_bar.set_progress(base_progress + current_fraction)
    
    def file_completed(self):
        """Mark a file as completed."""
        self._completed_files_count += 1
    
    def reset(self):
        """Reset progress bars and counters."""
        self._completed_files_count = 0
        self.file_progress_bar.set_progress(0, animate=False)
        self.total_progress_bar.set_progress(0, animate=False)
