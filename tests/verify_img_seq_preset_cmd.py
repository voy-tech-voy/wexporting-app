import sys
import os
import yaml
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from client.plugins.presets.logic.builder import CommandBuilder
from client.plugins.presets.logic.models import PresetDefinition

# Mock Registry
class MockRegistry:
    def get_tool_path(self, tool_id):
        if tool_id == 'ffmpeg':
            return "ffmpeg.exe"
        return None

def verify_preset():
    try:
        print("Initializing components...")
        registry = MockRegistry()
        builder = CommandBuilder(registry)
        
        # Load preset directly
        preset_path = r"client\plugins\presets\assets\presets\utilities\img_sequence_toVideo.yaml"
        current_dir = os.getcwd()
        full_path = os.path.join(current_dir, preset_path)
        
        print(f"Loading preset from: {full_path}")
        
        with open(full_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
            
        # Manually construct PresetDefinition since we can't import everything easily
        # The CommandBuilder only needs a lightweight object with 'pipeline' and 'parameters'
        # But we use the real class if possible.
        
        preset = PresetDefinition(
            id=raw_data['meta']['id'],
            name=raw_data['meta']['name'],
            category=raw_data['meta']['category'],
            description=raw_data['meta']['description'],
            version=raw_data['meta']['version'],
            raw_yaml=raw_data,
            is_available=True
        )
        
        print(f"Loaded preset: {preset.name}")
        
        # Test Context
        context = {
            'input_path': r'C:\Users\Test\Images\sequence_0001.png',
            'output_path': r'C:\Users\Test\Images\sequence_assembled.mp4',
            'output_path_no_ext': r'C:\Users\Test\Images\sequence',
            'meta': {'fps': 24.0, 'width': 1920, 'height': 1080}, # 16:9
            'tool_exe': 'ffmpeg.exe',
            'is_sequence': True,
            
            # User Params
            'framerate': '60',
            'quality': 5  # New min value
        }
        
        print("\n--- Test 1: Standard 1080p Input ---")
        commands = builder.build_pipeline(preset, context)
        
        if not commands:
            print("ERROR: No commands generated")
            return

        cmd = commands[0]
        readable_cmd = ' '.join(cmd.split())
        print(f"Command:\n{readable_cmd}\n")
        
        # Verify
        if "-crf 5" in readable_cmd: print("[PASS] CRF 5") 
        else: print("[FAIL] CRF 5 missing")
        
        if "pad=ceil(iw/2)*2" in readable_cmd: print("[PASS] Native Padding") 
        else: print("[FAIL] Padding missing")
        
        if "scale=" in readable_cmd: print("[FAIL] Scale filter found") 
        else: print("[PASS] No Scale filter")
        
        
        print("\n--- Test 2: Odd Resolution (1081p) Input ---")
        context['meta'] = {'fps': 24.0, 'width': 1920, 'height': 1081}
        commands_odd = builder.build_pipeline(preset, context)
        cmd_odd = commands_odd[0]
        readable_odd = ' '.join(cmd_odd.split())
        
        if "pad=ceil(iw/2)*2" in readable_odd: print("[PASS] Padding handles odd dimensions")
        else: print("[FAIL] Padding logic broken")

    except Exception as e:
        print(f"Error executing verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_preset()
