"""
Estimator Version Selector Widget

Reusable component for selecting estimator versions across all tabs.
Automatically populates based on media type and format/codec.
"""
from PySide6.QtWidgets import QWidget, QComboBox, QLabel, QHBoxLayout
from PySide6.QtCore import Signal as Signal
from typing import Optional


class EstimatorVersionSelector(QWidget):
    """
    Reusable widget for selecting estimator versions.
    
    Features:
    - Automatically scans filesystem for available versions
    - Defaults to highest version available
    - Only visible in dev mode
    - Emits signal when version changes
    
    Usage:
        selector = EstimatorVersionSelector('video', self)
        selector.set_format('MP4 (H.264)')
        selector.set_dev_mode(True)
        version = selector.get_selected_version()
    """
    
    version_changed = Signal(str)  # Emits version key (e.g., 'v6')
    
    def __init__(self, media_type: str, parent=None):
        """
        Initialize the version selector.
        
        Args:
            media_type: 'image', 'video', or 'loop'
            parent: Parent widget
        """
        super().__init__(parent)
        self.media_type = media_type
        self._current_format = None
        self._is_dev_mode = False
        
        # Create UI components
        self.label = QLabel("Estimator:")
        self.label.setStyleSheet("color: #888;")
        
        self.combo = QComboBox()
        self.combo.setToolTip("[DEV] Switch size estimation algorithm")
        # Let combo box expand to fill available width
        self.combo.setSizePolicy(self.combo.sizePolicy().horizontalPolicy(), self.combo.sizePolicy().verticalPolicy())
        self.combo.currentIndexChanged.connect(self._on_selection_changed)
        
        # Layout
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.label)
        layout.addWidget(self.combo, 1)  # Stretch factor 1 to fill available width
        self.setLayout(layout)
        
        # Start hidden (only visible in dev mode)
        self.setVisible(False)
    
    def set_format(self, format_or_codec: str):
        """
        Update available versions when format/codec changes.
        
        Args:
            format_or_codec: Format (JPG, WebP) or codec (H.264, VP9)
        """
        if self._current_format == format_or_codec:
            return
        
        self._current_format = format_or_codec
        self._populate_versions()
    
    def set_dev_mode(self, is_dev: bool):
        """
        Show/hide based on dev mode.
        
        Args:
            is_dev: True to show in dev mode, False to hide
        """
        self._is_dev_mode = is_dev
        self.setVisible(is_dev)
    
    def get_selected_version(self) -> Optional[str]:
        """
        Get currently selected version, or None if not in dev mode.
        
        Returns:
            Version string (e.g., 'v6') or None
        """
        if not self._is_dev_mode or not self.isVisible():
            return None
        return self.combo.currentData()
    
    def _populate_versions(self):
        """Scan filesystem and populate dropdown with available versions."""
        from client.core.target_size.size_estimator_registry import get_available_versions_for_format
        
        if not self._current_format:
            return
        
        # Block signals while updating
        self.combo.blockSignals(True)
        self.combo.clear()
        
        # Get available versions for this format
        versions = get_available_versions_for_format(self.media_type, self._current_format)
        
        if not versions:
            # No versions found, add placeholder
            self.combo.addItem("v2 (default)", "v2")
        else:
            # Add all available versions
            for display_name, version_key in versions:
                self.combo.addItem(display_name, version_key)
        
        # Auto-select highest version (last in sorted list)
        if versions:
            highest_idx = len(versions) - 1
            self.combo.setCurrentIndex(highest_idx)
        
        # Re-enable signals and emit change
        self.combo.blockSignals(False)
        self._on_selection_changed(self.combo.currentIndex())
    
    def _on_selection_changed(self, index: int):
        """
        Handle version selection change.
        
        Args:
            index: Combo box index
        """
        version = self.combo.itemData(index)
        if version:
            self.version_changed.emit(version)
            print(f"[{self.media_type.capitalize()}VersionSelector] Version changed to: {version}")
