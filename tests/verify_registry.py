
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client.core.tool_registry import get_registry

def test_registry():
    print("Testing ToolRegistry...")
    registry = get_registry()
    
    # Register bundled tools (they are registered in __init__.py of tool_registry)
    # But get_registry() calls _register_default_tools() so we are good.
    
    # Test get_bundled_path
    try:
        ffmpeg = registry.get_bundled_path('ffmpeg')
        print(f"FFmpeg bundled path: {ffmpeg}")
        
        magick = registry.get_bundled_path('magick')
        print(f"ImageMagick bundled path: {magick}")
        
    except AttributeError as e:
        print(f"FAILED: Method missing: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
        
    print("SUCCESS: ToolRegistry has get_bundled_path method")

if __name__ == "__main__":
    test_registry()
