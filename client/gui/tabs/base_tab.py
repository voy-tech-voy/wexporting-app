"""
BaseTab - Abstract Base Class for CommandPanel Tabs

Part of the Mediator-Shell architecture refactoring.
Each tab (Image, Video, Loop) inherits from this base.
"""

from abc import ABCMeta, abstractmethod
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal


# Combine Qt metaclass with ABCMeta to allow abstract methods in QWidget subclasses
class QABCMeta(type(QWidget), ABCMeta):
    """Combined metaclass for Qt widgets with ABC support."""
    pass


class BaseTab(QWidget, metaclass=QABCMeta):
    """
    Abstract base class for CommandPanel tabs.
    
    Provides common interface for:
    - UI setup
    - Parameter collection
    - Theme updates
    
    Subclasses must implement:
    - setup_ui(): Create the tab's UI elements
    - get_params(): Return dict of conversion parameters
    - update_theme(): Apply dark/light theme styling
    """
    
    # Signal emitted when parameters change (for live preview, etc.)
    params_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark_theme = True
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
    
    @abstractmethod
    def setup_ui(self):
        """
        Create the tab's UI elements.
        
        Called once during initialization.
        Subclasses should create all widgets and layouts here.
        """
        pass
    
    @abstractmethod
    def get_params(self) -> dict:
        """
        Collect current parameter values from UI elements.
        
        Returns:
            dict: Conversion parameters for this tab type
        """
        pass
    
    @abstractmethod
    def update_theme(self, is_dark: bool):
        """
        Apply theme styling to all tab elements.
        
        Args:
            is_dark: True for dark theme, False for light theme
        """
        pass
    
    @property
    def is_dark_theme(self) -> bool:
        """Current theme state."""
        return self._is_dark_theme
    
    def _emit_params_changed(self):
        """Convenience method for subclasses to emit params_changed signal."""
        self.params_changed.emit()
    
    # -------------------------------------------------------------------------
    # COMMON HELPER METHODS (Available to all tabs)
    # -------------------------------------------------------------------------
    
    def _create_section_header(self, title: str) -> QWidget:
        """
        Create a styled section header widget.
        
        Args:
            title: The section title text
            
        Returns:
            QWidget: Styled header widget
        """
        from PyQt6.QtWidgets import QLabel, QFrame
        from PyQt6.QtCore import Qt
        from client.gui.theme import Theme
        
        header = QFrame()
        header.setObjectName("SectionHeader")
        
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 10, 0, 5)
        
        label = QLabel(title.upper())
        label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.text_secondary()};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
        """)
        layout.addWidget(label)
        
        return header
    
    def _create_preset_button(self, parent_group):
        """
        Create and add custom preset button to the given group.
        
        This is a common pattern across all tabs, extracted to reduce boilerplate.
        
        Args:
            parent_group: The FormGroup to add the button to
            
        Returns:
            CustomPresetButton: The created button instance
        """
        from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy
        from client.gui.widgets.custom_preset_button import CustomPresetButton
        
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        
        self.custom_preset_btn = CustomPresetButton()
        self.custom_preset_btn.setVisible(True)  # Always visible
        button_layout.addWidget(self.custom_preset_btn)
        button_layout.addStretch()
        
        parent_group.add_row(button_container)
        return self.custom_preset_btn
    
    def _notify_param_change(self):
        """Called by subclasses when any parameter value changes."""
        self._emit_params_changed()
