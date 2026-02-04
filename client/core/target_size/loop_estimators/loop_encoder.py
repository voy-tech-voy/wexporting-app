"""
Loop Encoder - Performs GIF and WebM loop encoding.
Uses parameters calculated by loop estimators.
"""
import os
import ffmpeg
from typing import Dict, Optional, Callable


def encode_loop(
    input_path: str,
    output_path: str,
    params: Dict,
    output_format: str = 'GIF',
    status_callback: Optional[Callable[[str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> bool:
    """
    Encode video/image to loop format (GIF or WebM) using estimator params.
    
    Args:
        input_path: Source video/image file
        output_path: Destination file path
        params: Dict from optimize_gif_params() containing:
            - fps: int
            - colors: int
            - dither: str
            - resolution_scale: float
        output_format: 'GIF' or 'WebM'
        status_callback: Optional callback for status updates
        stop_check: Optional callback that returns True if should stop
        
    Returns:
        True if encoding succeeded, False otherwise
    """
    def emit_status(msg: str):
        if status_callback:
            status_callback(msg)
    
    try:
        format_lower = output_format.lower()
        
        if 'gif' in format_lower:
            # Extract GIF parameters
            fps = params.get('fps', 15)
            colors = params.get('colors', 128)
            dither = params.get('dither', 'bayer:bayer_scale=2')
            scale = params.get('resolution_scale', 1.0)
            
            emit_status(f"Encoding GIF: {fps}fps, {colors} colors, scale {int(scale * 100)}%")
            
            # Get metadata for scaling
            probe = ffmpeg.probe(input_path)
            video = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            if not video:
                emit_status("[X] No video stream found")
                return False
            
            width = int(video['width'])
            height = int(video['height'])
            target_w = int(width * scale)
            target_h = int(height * scale)
            
            # Extract dither type (remove parameters)
            dither_type = dither.split(':')[0] if ':' in dither else dither
            
            # Build FFmpeg command for GIF with palette
            input_stream = ffmpeg.input(input_path)
            
            # Apply FPS and scaling
            stream = input_stream.filter('fps', fps).filter('scale', target_w, target_h)
            
            # Generate palette
            palette_filter = f"palettegen=max_colors={colors}"
            
            # Use paletteuse with dither
            filter_complex = f"[0:v]fps={fps},scale={target_w}:{target_h}[v];[v]split[a][b];[a]{palette_filter}[p];[b][p]paletteuse=dither={dither_type}"
            
            # Output GIF
            output = ffmpeg.output(
                input_stream,
                output_path,
                filter_complex=filter_complex
            )
            output = ffmpeg.overwrite_output(output)
            
            # Run encoding
            ffmpeg.run(output, quiet=True)
            
        elif 'webm' in format_lower:
            emit_status("WebM loop encoding not yet implemented")
            return False
        else:
            emit_status(f"Unknown format: {output_format}")
            return False
        
        # Verify output
        if os.path.exists(output_path):
            actual_size = os.path.getsize(output_path)
            emit_status(f"[OK] Complete: {actual_size / 1024:.1f} KB")
            return True
        else:
            emit_status("[X] Output file not created")
            return False
            
    except Exception as e:
        if status_callback:
            status_callback(f"Error: {str(e)}")
        return False
