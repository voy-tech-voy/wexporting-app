"""
Development and Debugging Tools

Contains debug utilities for the application.
These should only be active in development/debug modes.
"""

from PySide6.QtCore import QObject, QEvent, Qt


DEBUG_INTERACTIVITY = True


class EventDebugFilter(QObject):
    """
    Debug event filter that logs interactive events to console.
    
    Tracks:
    - Preset button clicks and mode status
    - Lab button clicks and target type (Image/Video/Loop)
    - Click hierarchy information
    
    Install on QApplication to capture all events:
        filter = EventDebugFilter()
        QApplication.instance().installEventFilter(filter)
    """
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            # Only care about left click press for triggering actions
            if hasattr(event, 'button') and event.button() != Qt.MouseButton.LeftButton:
                return False
                
            # Helper to get hierarchy
            def get_hierarchy(w):
                chain = []
                curr = w
                while curr:
                    name = curr.objectName() or curr.__class__.__name__
                    chain.append(name)
                    curr = curr.parent()
                return " -> ".join(chain)
            
            hierarchy = get_hierarchy(obj)
            
            # --- 1. PRESETS STATUS ---
            top_level = None
            if hasattr(obj, 'window'):
                top_level = obj.window()
            
            preset_mode = "OFF"
            if top_level and hasattr(top_level, 'preset_status_btn'):
                if top_level.preset_status_btn._is_active:
                    preset_mode = "ON"
            
            # --- 2. DETECT LAB CLICK ---
            lab_action = None
            
            # Check hierarchy for MorphingButton
            curr = obj
            while curr:
                if "MorphingButton" in curr.__class__.__name__:
                    # Found Lab Button
                    mb = curr
                    # Check if obj is one of the sub-items
                    if hasattr(mb, '_items') and obj in mb._items:
                        idx = mb._items.index(obj)
                        type_map = {0: "IMAGE", 1: "VIDEO", 2: "LOOP"}
                        lab_action = type_map.get(idx, "UNKNOWN")
                    break
                curr = curr.parent()
            
            if lab_action:
                print(f"\n>>> DEBUG EVENT: Click inside Lab Button")
                print(f"    Preset Mode: {preset_mode}")
                print(f"    Target: {lab_action}")
            elif "PresetStatusButton" in hierarchy:
                print(f"\n>>> DEBUG EVENT: Click on Preset Button")
                print(f"    Current Mode: {preset_mode}")
                
            return False
                         
        return super().eventFilter(obj, event)
