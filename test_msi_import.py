import sys
import traceback
import importlib
import importlib.util

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

print("Starting import test...")

try:
    from client.core.tool_registry import get_registry
    print("✓ Successfully imported get_registry")
except Exception as e:
    print(f"✗ Failed to import get_registry: {e}")
    traceback.print_exc()

try:
    from client.plugins.presets.orchestrator import PresetOrchestrator
    print("✓ Successfully imported PresetOrchestrator")
except Exception as e:
    print(f"✗ Failed to import PresetOrchestrator: {e}")
    traceback.print_exc()

spec = importlib.util.find_spec("client.plugins.presets.ui.dynamic_parameter_panel")
if spec is None:
    print("✗ Could not find dynamic_parameter_panel spec")
else:
    print("✓ Found dynamic_parameter_panel spec")
    try:
        from client.plugins.presets.ui.dynamic_parameter_panel import DynamicParameterPanel
        print("✓ Successfully imported DynamicParameterPanel")
    except Exception as e:
        print(f"✗ Failed to import DynamicParameterPanel: {e}")
        traceback.print_exc()

print("Test complete.")
