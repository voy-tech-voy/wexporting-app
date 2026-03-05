"""
Central manager for all Developer Panels.
Handles registration, toggling, and keyboard shortcuts.
"""

import traceback
from PySide6.QtCore import Qt, QObject
from typing import Dict, Type, Optional

# Import panel classes (will be moved/refactored next)
# using string imports or postponed imports to avoid circular deps if needed

class DevPanelManager(QObject):
    """
    Manages lifecycle and visibility of dev panels.
    Designed to be used as a singleton or attached to MainWindow.
    """
    
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = DevPanelManager()
        return cls._instance

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.panels: Dict[str, QWidget] = {}
        self.panel_classes: Dict[str, Type] = {}
        
    def set_main_window(self, window):
        self.main_window = window

    def register_panel(self, key: str, panel_class: Type):
        """Register a panel class with a unique key."""
        self.panel_classes[key] = panel_class
        print(f"[DevManager] Registered panel '{key}': {panel_class.__name__}")

    def toggle_panel(self, key: str):
        """Toggle visibility of a registered panel."""
        if not self.main_window:
            print("[DevManager] Error: MainWindow not set")
            return

        if key in self.panels:
            panel = self.panels[key]
            if panel.isVisible():
                panel.close()
            else:
                panel.show()
                panel.raise_()
                panel.activateWindow()
        else:
            # Lazy instantiation
            if key in self.panel_classes:
                try:
                    panel = self.panel_classes[key](self.main_window)
                    self.panels[key] = panel

                    
                    # Panel-specific initialization
                    if key == 'purchase':
                        # Any specific init for purchase panel?
                        pass
                    if key == 'noise':
                        # Connect noise panel signal to refresh file list items
                        if hasattr(panel, 'params_changed') and hasattr(self.main_window, '_refresh_file_list_items'):
                            panel.params_changed.connect(self.main_window._refresh_file_list_items)
                            
                    elif key == 'sequence':
                        # Connect sequence panel signal to refresh file list items
                        if hasattr(panel, 'paramsChanged') and hasattr(self.main_window, '_refresh_file_list_items'):
                            panel.paramsChanged.connect(self.main_window._refresh_file_list_items)
                    
                    panel.show()
                except Exception as e:
                    print(f"[DevManager] Failed to create panel '{key}': {e}")
                    traceback.print_exc()
            else:
                # Try to import known panels dynamically if not registered
                if key == 'purchase':
                    from client.gui.dev_panels.purchase_panel import PurchaseDevPanel
                    self.register_panel('purchase', PurchaseDevPanel)
                    self.toggle_panel('purchase') # Retry
                else:
                    print(f"[DevManager] Unknown panel key: {key}")

    def handle_key_event(self, event):
        """Centralized key handler (to be called from MainWindow)."""
        if event.key() == Qt.Key.Key_F11:
            self.toggle_panel('sequence') # F11 for Sequence Params
            event.accept()
            return True
        elif event.key() == Qt.Key.Key_F12:
            self.toggle_panel('theme') # F12 for Theme
            event.accept()
            return True
        elif event.key() == Qt.Key.Key_F10:
            self.toggle_panel('noise') # F10 for Noise
            event.accept()
            return True
        elif event.key() == Qt.Key.Key_F9:
            self.toggle_panel('purchase') # F9 for Purchase Style
            event.accept()
            return True
        return False
