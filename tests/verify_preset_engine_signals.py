
import sys
import os
from PyQt6.QtCore import QObject

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock PresetOrchestrator to avoid complex dependencies
class MockOrchestrator(QObject):
    def __init__(self):
        super().__init__()

def test_signals():
    print("Testing PresetConversionEngine signals...")
    try:
        from client.plugins.presets.engine.preset_conversion_engine import PresetConversionEngine
        
        # Instantiate engine
        orchestrator = MockOrchestrator()
        engine = PresetConversionEngine([], {}, orchestrator)
        
        # Check for signals
        signals = [
            'file_skipped',
            'file_failed',
            'file_stopped',
            'file_completed',
            'progress_updated',
            'file_progress_updated',
            'status_updated',
            'conversion_completed'
        ]
        
        missing = []
        for sig in signals:
            if not hasattr(engine, sig):
                missing.append(sig)
            else:
                print(f"[OK] Signal found: {sig}")
        
        if missing:
            print(f"FAILED: Missing signals: {missing}")
            sys.exit(1)
            
        print("SUCCESS: All required signals are present.")
        
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_signals()
