import sys
import os
import yaml
import jinja2

def to_ffmpeg_pattern(path):
    # Mock filter
    return path.replace("0001", "%04d")

def verify_preset():
    try:
        print("Initializing verification...")
        
        # Load preset directly
        preset_path = r"client\plugins\presets\assets\presets\utilities\img_sequence_toVideo.yaml"
        current_dir = os.getcwd()
        full_path = os.path.join(current_dir, preset_path)
        
        print(f"Loading preset from: {full_path}")
        
        with open(full_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
            
        template_str = raw_data['pipeline'][0]['command_template']
        
        # Setup Jinja2 environment
        env = jinja2.Environment()
        env.filters['to_ffmpeg_pattern'] = to_ffmpeg_pattern
        template = env.from_string(template_str)
        
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
        rendered = template.render(**context)
        readable_cmd = ' '.join(rendered.split())
        print(f"Command:\n{readable_cmd}\n")
        
        # Verify
        if "-crf 5" in readable_cmd: print("[PASS] CRF 5") 
        else: print("[FAIL] CRF 5 missing")
        
        if "pad=ceil(iw/2)*2" in readable_cmd: print("[PASS] Native Padding") 
        else: print("[FAIL] Padding missing")
        
        if "scale=" in readable_cmd: print("[FAIL] Scale filter found") 
        else: print("[PASS] No Scale filter")
        
        if "-framerate 60" in readable_cmd: print("[PASS] Framerate 60")
        else: print("[FAIL] Framerate missing")
        
        
        print("\n--- Test 2: Odd Resolution (1081p) Input ---")
        context['meta'] = {'fps': 24.0, 'width': 1920, 'height': 1081}
        rendered_odd = template.render(**context)
        readable_odd = ' '.join(rendered_odd.split())
        
        if "pad=ceil(iw/2)*2" in readable_odd: print("[PASS] Padding handles odd dimensions")
        else: print("[FAIL] Padding logic broken")
        
        print("\n--- Test 3: Auto Framerate ---")
        context['framerate'] = "Auto"
        context['meta']['fps'] = 24.0
        rendered_auto = template.render(**context)
        readable_auto = ' '.join(rendered_auto.split())
        
        if "-framerate 24.0" in readable_auto: print("[PASS] Auto framerate used meta.fps")
        else: print(f"[FAIL] Auto framerate failed: {readable_auto}")

    except Exception as e:
        print(f"Error executing verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_preset()
