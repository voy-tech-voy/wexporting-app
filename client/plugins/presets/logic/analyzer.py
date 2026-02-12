"""
Presets Plugin - Media Analyzer

Extracts video metadata using FFprobe for smart preset logic.
Provides the `meta` context object for Jinja2 templates.
"""
import subprocess
import json
import os
from typing import Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from client.core.tool_registry.protocol import ToolRegistryProtocol


class MediaAnalyzer:
    """
    Extracts media metadata using FFprobe.
    
    Provides the `meta` dict for Jinja2 template context:
    - meta.fps: Frame rate (float)
    - meta.width: Video width (int)
    - meta.height: Video height (int)
    - meta.duration: Duration in seconds (float)
    - meta.is_landscape: True if width > height
    - meta.has_audio: True if audio stream present
    - meta.codec: Video codec name
    """
    
    def __init__(self, registry: 'ToolRegistryProtocol'):
        """
        Initialize with ToolRegistry for FFprobe path resolution.
        
        Args:
            registry: Tool registry (FFprobe is companion to FFmpeg)
        """
        self._registry = registry
        self._ffprobe_path = self._get_ffprobe_path()
    
    def _get_ffprobe_path(self) -> Optional[str]:
        """Get FFprobe path from FFmpeg's directory."""
        ffmpeg_path = self._registry.get_tool_path("ffmpeg")
        if not ffmpeg_path:
            return None
        
        ffmpeg_dir = Path(ffmpeg_path).parent
        
        # Try common ffprobe names
        for name in ["ffprobe.exe", "ffprobe"]:
            probe_path = ffmpeg_dir / name
            if probe_path.exists():
                return str(probe_path)
        
        return None
    
    def analyze(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a media file and return metadata.
        
        Args:
            file_path: Path to media file
            
        Returns:
            Dict with metadata fields (fps, width, height, duration, etc.)
        """
        if not self._ffprobe_path:
            return self._get_defaults()
        
        try:
            cmd = [
                self._ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid chars instead of crashing
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode != 0:
                print(f"[MediaAnalyzer] FFprobe failed: {result.stderr[:200]}")
                return self._get_defaults()
            
            probe_data = json.loads(result.stdout)
            return self._parse_probe_data(probe_data)
            
        except subprocess.TimeoutExpired:
            print(f"[MediaAnalyzer] FFprobe timeout for {file_path}")
            return self._get_defaults()
        except json.JSONDecodeError as e:
            print(f"[MediaAnalyzer] JSON parse error: {e}")
            return self._get_defaults()
        except Exception as e:
            print(f"[MediaAnalyzer] Error analyzing {file_path}: {e}")
            return self._get_defaults()
    
    def _parse_probe_data(self, data: Dict) -> Dict[str, Any]:
        """Parse FFprobe JSON output into clean meta dict."""
        meta = self._get_defaults()
        
        # Get video stream
        video_stream = None
        audio_stream = None
        
        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_stream is None:
                video_stream = stream
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = stream
        
        if video_stream:
            # Dimensions
            meta["width"] = video_stream.get("width", 0)
            meta["height"] = video_stream.get("height", 0)
            meta["is_landscape"] = meta["width"] > meta["height"]
            
            # FPS - parse "30/1" or "60000/1001" format
            fps_str = video_stream.get("r_frame_rate", "30/1")
            try:
                num, den = map(int, fps_str.split("/"))
                meta["fps"] = round(num / den, 2) if den else 30.0
            except:
                meta["fps"] = 30.0
            
            # Codec
            meta["codec"] = video_stream.get("codec_name", "unknown")
            
            # Bitrate
            if "bit_rate" in video_stream:
                try:
                    meta["bitrate"] = int(video_stream["bit_rate"])
                except:
                    pass
        
        # Audio
        meta["has_audio"] = audio_stream is not None
        
        # Duration from format
        format_data = data.get("format", {})
        if "duration" in format_data:
            try:
                meta["duration"] = float(format_data["duration"])
            except:
                pass
        
        return meta
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Get default metadata values when analysis fails."""
        return {
            "fps": 24.0,
            "width": 1920,
            "height": 1080,
            "duration": 0.0,
            "is_landscape": True,
            "has_audio": True,
            "codec": "unknown",
            "bitrate": 0
        }
    
    def is_available(self) -> bool:
        """Check if FFprobe is available."""
        return self._ffprobe_path is not None
