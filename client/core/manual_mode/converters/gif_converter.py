"""GIF converter for manual mode"""

import os
from pathlib import Path
from typing import Dict, Any

import ffmpeg

from .base_converter import BaseConverter
from client.core.tool_registry import get_ffmpeg_path, get_ffprobe_path


class GifConverter(BaseConverter):
    """
    Handles GIF conversion in manual mode (video to GIF)
    
    Supports: GIF output from video files
    Applies: FPS, Colors, Dither, Resize, Rotation, Time Cutting, Retime
    """
    
    # GIF is both input (pass-through) and output format
    SUPPORTED_FORMATS = {'.gif', '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.flv', '.wmv'}
    
    def get_supported_extensions(self) -> set:
        return self.SUPPORTED_FORMATS
    
    def convert(self, file_path: str, output_path: str) -> bool:
        """
        Convert video to GIF using FFmpeg
        
        Args:
            file_path: Source file path (video or GIF)
            output_path: Output GIF path (from SuffixManager)
            
        Returns:
            True if successful, False otherwise
        """
        print(f"\n[GifConverter] Starting GIF conversion")
        print(f"[GifConverter] Input: {file_path}")
        print(f"[GifConverter] Output: {output_path}")
        print(f"[GifConverter] Params: {self.params}")
        
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            print(f"[GifConverter] Output directory created/verified")
            
            # Build FFmpeg pipeline
            print(f"[GifConverter] Building input stream...")
            stream = self._build_input_stream(file_path)
            print(f"[GifConverter] Applying filters...")
            stream = self._apply_filters(stream, file_path)
            print(f"[GifConverter] Building output args...")
            output_args = self._build_output_args()
            print(f"[GifConverter] Output args: {output_args}")
            
            output = ffmpeg.output(stream, output_path, **output_args)
            
            if self.params.get('overwrite', False):
                output = ffmpeg.overwrite_output(output)
            
            # Execute
            self.emit_status(f"Converting to GIF: {Path(file_path).name}")
            
            ffmpeg_cmd = get_ffmpeg_path()
            print(f"[GifConverter] FFmpeg command: {ffmpeg_cmd}")
            print(f"[GifConverter] Executing FFmpeg...")
            
            # Get video duration for progress tracking
            from client.core.ffmpeg_utils import get_video_duration
            total_duration = get_video_duration(file_path)
            
            # Apply time cutting adjustments
            if self.params.get('enable_time_cutting'):
                time_start = self.params.get('time_start', 0)
                time_end = self.params.get('time_end', 1)
                total_duration = total_duration * (time_end - time_start)
            
            # Apply retime adjustments
            if self.params.get('retime_enabled') or self.params.get('enable_retime'):
                retime_speed = self.params.get('retime_speed', 1.0)
                if retime_speed and retime_speed > 0:
                    total_duration = total_duration / retime_speed
            
            print(f"[GifConverter] Total duration for progress: {total_duration:.2f}s")
            
            # Use progress tracking for GIF (has duration)
            if total_duration > 0 and self.progress_callback:
                success = self.run_ffmpeg_with_progress(output, ffmpeg_cmd, total_duration)
            else:
                # Fallback to standard run
                ffmpeg.run(
                    output,
                    cmd=ffmpeg_cmd,
                    capture_stdout=True,
                    capture_stderr=True,
                    quiet=True
                )
                success = True
            
            if success:
                self.emit_status(f"[OK] {Path(output_path).name}")
                return True
            else:
                return False
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            self.emit_status(f"GIF conversion error: {error_msg[:200]}")
            print(f"GIF conversion FFmpeg error for {file_path}: {error_msg}")
            return False
        except Exception as e:
            self.emit_status(f"GIF conversion error: {str(e)}")
            print(f"GIF conversion error for {file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _build_input_stream(self, file_path: str):
        """Build FFmpeg input stream with time cutting if enabled"""
        input_args = self._get_input_args()
        return ffmpeg.input(file_path, **input_args)
    
    def _get_input_args(self) -> Dict[str, Any]:
        """Get input arguments (for time cutting)"""
        args = {}
        
        # Time cutting (seek to start, duration)
        if self.params.get('enable_time_cutting'):
            time_start = self.params.get('time_start', 0)  # Normalized 0-1
            time_end = self.params.get('time_end', 1)
            
            if time_start is not None and time_end is not None and time_start != time_end:
                # Get actual duration - would need ffprobe, for now use normalized values
                # FFmpeg will handle the normalized values
                args['ss'] = time_start
                if time_end < 1.0:
                    args['to'] = time_end
        
        return args
    
    def _apply_filters(self, stream, file_path: str):
        """Apply all GIF filters in correct order"""
        print(f"[GifConverter] Applying filters...")
        
        # 1. Apply retime/speed change first (affects timing)
        if self.params.get('retime_enabled') or self.params.get('enable_retime'):
            retime_speed = self.params.get('retime_speed', 1.0)
            if retime_speed and retime_speed != 1.0:
                print(f"[GifConverter] Applying retime: {retime_speed}x")
                stream = self._apply_retime(stream, retime_speed)
        
        # 2. Apply resize
        current_resize = self.params.get('current_resize')
        if current_resize:
            print(f"[GifConverter] Applying resize: {current_resize}")
            stream = self._apply_resize(stream, current_resize)
        
        # 3. Apply rotation
        rotation = self.params.get('rotation_angle', 'No rotation')
        if rotation != 'No rotation':
            print(f"[GifConverter] Applying rotation: {rotation}")
            stream = self._apply_rotation(stream, rotation)
        
        # 4. Apply GIF palette optimization
        fps = self.params.get('gif_fps', 15)
        colors = self.params.get('gif_colors', 256)
        dither = self.params.get('gif_dither', 'bayer')
        print(f"[GifConverter] Applying GIF optimization - fps:{fps}, colors:{colors}, dither:{dither}")
        
        stream = self._apply_gif_optimization(stream, fps, colors, dither)
        
        return stream
    
    def _apply_retime(self, stream, speed: float):
        """Apply speed change (retime) to video stream"""
        # Video: setpts filter (divide by speed)
        # Audio: atempo filter (multiply by speed)
        pts_factor = 1.0 / speed
        stream = ffmpeg.filter(stream, 'setpts', f'{pts_factor}*PTS')
        
        # Note: GIF has no audio, so no atempo needed
        return stream
    
    def _apply_resize(self, stream, resize_value: str):
        """Apply resize filter"""
        if not resize_value or resize_value == 'No resize':
            return stream
        
        # Percentage resize
        if isinstance(resize_value, str) and resize_value.endswith('%'):
            percent = float(resize_value[:-1]) / 100.0
            # Ensure even dimensions for GIF
            w_expr = f'trunc(iw*{percent}/2)*2'
            h_expr = f'trunc(ih*{percent}/2)*2'
            return ffmpeg.filter(stream, 'scale', w=w_expr, h=h_expr)
        
        # Longer edge resize
        if isinstance(resize_value, str) and resize_value.startswith('L'):
            target_longer_edge = int(resize_value[1:])
            # Scale so longer edge = target, shorter maintains aspect (even dimensions)
            return ffmpeg.filter(
                stream, 'scale',
                w=f'trunc(if(gte(iw\\,ih)\\,{target_longer_edge}\\,iw*{target_longer_edge}/ih)/2)*2',
                h=f'trunc(if(lt(iw\\,ih)\\,{target_longer_edge}\\,ih*{target_longer_edge}/iw)/2)*2'
            )
        
        # Width-based resize (maintain aspect, even dimensions)
        width = int(resize_value)
        return ffmpeg.filter(stream, 'scale', w=width, h=-2)
    
    def _apply_rotation(self, stream, rotation: str):
        """Apply rotation filter"""
        if rotation == '90° clockwise':
            return ffmpeg.filter(stream, 'transpose', 1)
        elif rotation == '180°':
            stream = ffmpeg.filter(stream, 'transpose', 2)
            stream = ffmpeg.filter(stream, 'transpose', 2)
            return stream
        elif rotation == '270° clockwise':
            return ffmpeg.filter(stream, 'transpose', 2)
        
        return stream
    
    def _apply_gif_optimization(self, stream, fps: int, colors: int, dither: str):
        """
        Apply GIF palette optimization using FFmpeg's palettegen and paletteuse
        
        This is the standard FFmpeg two-pass GIF optimization:
        1. Generate optimal palette for the video
        2. Apply palette with dithering
        """
        # Map dither UI names to FFmpeg dither algorithms
        dither_map = {
            'none': 'none',
            'bayer': 'bayer',
            'floyd_steinberg': 'floyd_steinberg',
            'sierra2': 'sierra2',
            'sierra2_4a': 'sierra2_4a'
        }
        
        # Handle numeric dither values (0-5 scale)
        if isinstance(dither, (int, str)):
            try:
                dither_value = int(dither)
                dither_names = ['none', 'bayer', 'bayer', 'bayer', 'floyd_steinberg', 'sierra2']
                dither = dither_names[min(dither_value, len(dither_names) - 1)]
            except (ValueError, TypeError):
                pass
        
        ffmpeg_dither = dither_map.get(dither, 'bayer')
        
        # Set FPS
        stream = ffmpeg.filter(stream, 'fps', fps)
        
        # Split stream for palette generation (correct ffmpeg-python syntax)
        split = stream.split()
        
        # Generate palette from first split output
        palette = ffmpeg.filter(
            split[0],
            'palettegen',
            max_colors=colors,
            stats_mode='diff'
        )
        
        # Apply palette with dithering using second split output
        stream = ffmpeg.filter(
            [split[1], palette],
            'paletteuse',
            dither=ffmpeg_dither
        )
        
        return stream
    
    def _build_output_args(self) -> Dict[str, Any]:
        """Build FFmpeg output arguments for GIF"""
        args = {
            'format': 'gif',
            'loop': 0  # Infinite loop
        }
        
        return args
    
    def get_format_extension(self) -> str:
        """Always return 'gif' for GIF converter"""
        return 'gif'
