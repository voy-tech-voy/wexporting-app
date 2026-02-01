"""
Target Size Conversion Engine - Dedicated converter for Max Size mode (v2)
Uses 2-pass bitrate encoding to achieve target file sizes.

This is a completely separate conversion engine from the main one,
designed specifically for target size based conversions.
"""

import os
import ffmpeg
from pathlib import Path
from typing import Dict, Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal

from .size_estimator_registry import (
    optimize_video_params,
    optimize_image_params,
    optimize_gif_params
)
from .suffix_manager import get_output_path
from ._common import get_media_metadata
from client.core.ffmpeg_utils import (
    get_video_dimensions,
    get_video_duration,
    has_audio_stream,
)


class TargetSizeConversionEngine(QThread):
    """
    Conversion engine for target size mode (v2 estimator).
    Uses bitrate-based encoding to achieve specific file sizes.
    """
    
    # Signals
    progress_updated = pyqtSignal(int)
    file_progress_updated = pyqtSignal(int, float)
    status_updated = pyqtSignal(str)
    file_completed = pyqtSignal(str, str)
    conversion_completed = pyqtSignal(int, int)
    
    def __init__(self, files: list, params: Dict):
        super().__init__()
        self.files = files
        self.params = params
        self.should_stop = False
        self.successful_conversions = 0
        self.failed_conversions = 0
        
    def stop_conversion(self):
        """Stop the conversion process."""
        self.should_stop = True
        
    def run(self):
        """Main conversion thread execution."""
        total_files = len(self.files)
        
        for i, file_path in enumerate(self.files):
            if self.should_stop:
                break
                
            self.file_progress_updated.emit(i, 0.0)
            self.status_updated.emit(f"Processing: {os.path.basename(file_path)}")
            
            try:
                conversion_type = self.params.get('type', 'video')
                
                if conversion_type == 'video':
                    success = self._convert_video(file_path)
                elif conversion_type == 'image':
                    success = self._convert_image(file_path)
                elif conversion_type == 'loop':
                    success = self._convert_gif(file_path)
                else:
                    self.status_updated.emit(f"Unknown type: {conversion_type}")
                    success = False
                    
                if success:
                    self.successful_conversions += 1
                    self.file_completed.emit(file_path, "success")
                else:
                    self.failed_conversions += 1
                    self.file_completed.emit(file_path, "failed")
                    
            except Exception as e:
                self.status_updated.emit(f"Error: {str(e)}")
                self.failed_conversions += 1
                self.file_completed.emit(file_path, "failed")
                
            self.file_progress_updated.emit(i, 1.0)
            self.progress_updated.emit(int((i + 1) / total_files * 100))
            
        self.conversion_completed.emit(self.successful_conversions, self.failed_conversions)
        
    def _get_output_path(self, file_path: str, extension: str, optimal_params: Dict = None) -> str:
        """Generate output path using suffix manager."""
        return get_output_path(file_path, self.params, extension, optimal_params)
        
    def _convert_video(self, file_path: str) -> bool:
        """Convert video to target file size using 2-pass bitrate encoding."""
        try:
            # Get target size
            target_mb = self.params.get('video_max_size_mb', 5.0)
            target_bytes = int(target_mb * 1024 * 1024)
            auto_resize = self.params.get('video_auto_resize', False)
            
            # Get codec preference
            selected_codec = self.params.get('codec', 'H.264 (MP4)')
            
            # Determine output format
            output_ext = 'webm' if 'WebM' in selected_codec else 'mp4'
            
            self.status_updated.emit(f"[v2] Calculating optimal bitrate for {target_mb:.1f} MB target...")
            
            # Call v2 estimator directly
            optimal = optimize_video_params(
                file_path, 
                target_bytes, 
                codec_pref=selected_codec,
                allow_downscale=auto_resize
            )
            
            video_bitrate = optimal['video_bitrate_kbps']
            audio_bitrate = optimal['audio_bitrate_kbps']
            resolution_scale = optimal.get('resolution_scale', 1.0)
            codec = optimal['codec']  # CRITICAL: Use codec from estimator
            
            # Generate output path with optimal params for suffix
            output_path = self._get_output_path(file_path, output_ext, optimal_params=optimal)
            
            self.status_updated.emit(f"[v2] Using codec: {codec}, {video_bitrate}kbps video, {audio_bitrate}kbps audio")
            
            # Build FFmpeg filter chain
            input_stream = ffmpeg.input(file_path)
            video_stream = input_stream.video
            
            # Apply resolution scale if needed
            if resolution_scale < 1.0:
                meta = get_media_metadata(file_path)
                new_width = int(meta['width'] * resolution_scale)
                new_width = new_width - (new_width % 2)  # Ensure even
                video_stream = ffmpeg.filter(video_stream, 'scale', new_width, -2)
                self.status_updated.emit(f"[v2] Scaling to {int(resolution_scale * 100)}%")
                
            # Apply rotation if specified
            rotation = self.params.get('rotation_angle')
            if rotation and rotation != "No rotation":
                if rotation == "90° clockwise":
                    video_stream = ffmpeg.filter(video_stream, 'transpose', 1)
                elif rotation == "180°":
                    video_stream = ffmpeg.filter(video_stream, 'transpose', 2)
                    video_stream = ffmpeg.filter(video_stream, 'transpose', 2)
                elif rotation == "270° clockwise":
                    video_stream = ffmpeg.filter(video_stream, 'transpose', 2)
            
            # Prepare common encoding arguments
            encode_args = {
                'vcodec': codec,  # CRITICAL: Use codec from estimator
                'b:v': f'{video_bitrate}k',
                'maxrate': f'{int(video_bitrate * 1.5)}k',
                'bufsize': f'{int(video_bitrate * 2)}k',
            }
            
            # AV1 speed optimization
            if codec == 'libaom-av1':
                encode_args['cpu-used'] = 4
            
            # Handle audio
            has_audio = has_audio_stream(file_path)
            audio_stream = None
            if 'WebM' in selected_codec:
                # WebM: no audio
                encode_args['an'] = None
            elif has_audio:
                audio_stream = input_stream.audio
                encode_args['b:a'] = f'{audio_bitrate}k'
                encode_args['acodec'] = 'aac'
            
            # 2-Pass Encoding
            self.status_updated.emit(f"[v2] Pass 1/2: Analyzing video...")
            
            # PASS 1: Analyze and create log file
            pass1_args = encode_args.copy()
            pass1_args['f'] = 'null'
            pass1_args.update({'pass': 1})  # Use dict to avoid Python keyword conflict
            
            # Pass 1 output to null device
            if audio_stream:
                pass1_stream = ffmpeg.output(video_stream, audio_stream, 'NUL' if os.name == 'nt' else '/dev/null', **pass1_args)
            else:
                pass1_stream = ffmpeg.output(video_stream, 'NUL' if os.name == 'nt' else '/dev/null', **pass1_args)
            
            pass1_stream = ffmpeg.overwrite_output(pass1_stream)
            ffmpeg.run(pass1_stream, quiet=True)
            
            # PASS 2: Encode final output
            self.status_updated.emit(f"[v2] Pass 2/2: Encoding final video...")
            
            pass2_args = encode_args.copy()
            pass2_args.update({'pass': 2})  # Use dict to avoid Python keyword conflict
            
            if audio_stream:
                pass2_stream = ffmpeg.output(video_stream, audio_stream, output_path, **pass2_args)
            else:
                pass2_stream = ffmpeg.output(video_stream, output_path, **pass2_args)
                
            pass2_stream = ffmpeg.overwrite_output(pass2_stream)
            ffmpeg.run(pass2_stream, quiet=True)
            
            # Clean up pass log files
            try:
                for log_file in ['ffmpeg2pass-0.log', 'ffmpeg2pass-0.log.mbtree']:
                    if os.path.exists(log_file):
                        os.remove(log_file)
            except Exception:
                pass  # Ignore cleanup errors
            
            # Report result
            if os.path.exists(output_path):
                actual_size = os.path.getsize(output_path)
                actual_mb = actual_size / (1024 * 1024)
                self.status_updated.emit(f"[v2] ✓ Complete: {actual_mb:.2f} MB (target: {target_mb:.1f} MB)")
                return True
            else:
                self.status_updated.emit("[v2] ✗ Output file not created")
                return False
                
        except Exception as e:
            self.status_updated.emit(f"[v2] Error: {str(e)}")
            return False
            
    def _convert_image(self, file_path: str) -> bool:
        """Convert image to target file size."""
        print(f"[TargetSizeEngine] _convert_image called for: {file_path}")
        print(f"[TargetSizeEngine] Params: {self.params}")
        
        try:
            print(f"[TargetSizeEngine] Step 1: Getting params...")
            target_mb = self.params.get('image_max_size_mb', 1.0)
            target_bytes = int(target_mb * 1024 * 1024)
            auto_resize = self.params.get('image_auto_resize', False)
            print(f"[TargetSizeEngine] target_mb={target_mb}, target_bytes={target_bytes}, auto_resize={auto_resize}")
            
            # Get output format
            print(f"[TargetSizeEngine] Step 2: Getting output format...")
            output_format = self.params.get('format', 'jpg').lower()
            print(f"[TargetSizeEngine] output_format={output_format}")
            
            print(f"[TargetSizeEngine] Step 3: Emitting status...")
            self.status_updated.emit(f"[v2] Optimizing image for {target_mb:.3f} MB target...")
            
            print(f"[TargetSizeEngine] Step 4: Calling optimize_image_params...")
            # Call v2 estimator
            optimal = optimize_image_params(
                file_path,
                output_format,
                target_bytes,
                allow_downscale=auto_resize
            )
            
            print(f"[TargetSizeEngine] Step 5: Got optimal params: {optimal}")
            quality = optimal['quality']
            scale_factor = optimal.get('scale_factor', 1.0)
            
            print(f"[TargetSizeEngine] Step 6: Generating output path...")
            # Generate output path with optimal params for suffix
            output_path = self._get_output_path(file_path, output_format, optimal_params=optimal)
            print(f"[TargetSizeEngine] output_path={output_path}")
            
            self.status_updated.emit(f"[v2] Using quality {quality}, scale {int(scale_factor * 100)}%")
            
            print(f"[TargetSizeEngine] Step 7: Building FFmpeg command...")
            # Build FFmpeg command
            input_stream = ffmpeg.input(file_path)
            stream = input_stream
            
            # Apply scale if needed
            if scale_factor < 1.0:
                print(f"[TargetSizeEngine] Applying scale factor {scale_factor}...")
                meta = get_media_metadata(file_path)
                new_width = int(meta['width'] * scale_factor)
                stream = ffmpeg.filter(stream, 'scale', new_width, -1)
                
            # Output with quality
            print(f"[TargetSizeEngine] Step 8: Setting output params for format {output_format}...")
            if output_format in ['jpg', 'jpeg']:
                q_val = max(1, min(31, int((100 - quality) * 31 / 100)))
                stream = ffmpeg.output(stream, output_path, **{'q:v': q_val})
            elif output_format == 'webp':
                stream = ffmpeg.output(stream, output_path, quality=quality)
            else:
                stream = ffmpeg.output(stream, output_path)
                
            print(f"[TargetSizeEngine] Step 9: Running FFmpeg...")
            stream = ffmpeg.overwrite_output(stream)
            ffmpeg.run(stream, quiet=True)
            
            print(f"[TargetSizeEngine] Step 10: Checking output...")
            if os.path.exists(output_path):
                actual_size = os.path.getsize(output_path)
                actual_mb = actual_size / (1024 * 1024)
                self.status_updated.emit(f"[v2] ✓ Complete: {actual_mb:.2f} MB")
                print(f"[TargetSizeEngine] SUCCESS! File created: {output_path}, size: {actual_mb:.2f} MB")
                return True
            else:
                print(f"[TargetSizeEngine] FAILED! Output file not created: {output_path}")
                return False
            
        except Exception as e:
            import traceback
            error_msg = f"[v2] Image error: {str(e)}"
            print(f"[TargetSizeEngine] EXCEPTION: {error_msg}")
            print(f"[TargetSizeEngine] Traceback:\n{traceback.format_exc()}")
            self.status_updated.emit(error_msg)
            return False
            
    def _convert_gif(self, file_path: str) -> bool:
        """Convert video to GIF at target file size."""
        try:
            target_mb = self.params.get('gif_max_size_mb', 2.0)
            target_bytes = int(target_mb * 1024 * 1024)
            auto_resize = self.params.get('gif_auto_resize', False)
            
            self.status_updated.emit(f"[v2] Optimizing GIF for {target_mb:.1f} MB target...")
            
            # Call v2 estimator
            optimal = optimize_gif_params(
                file_path,
                target_bytes,
                allow_downscale=auto_resize
            )
            
            fps = optimal['fps']
            colors = optimal['colors']
            dither = optimal.get('dither', 'bayer:bayer_scale=3')
            resolution_scale = optimal.get('resolution_scale', 1.0)
            
            # Generate output path with optimal params for suffix
            output_path = self._get_output_path(file_path, 'gif', optimal_params=optimal)
            
            self.status_updated.emit(f"[v2] Using {fps}fps, {colors} colors, {int(resolution_scale * 100)}% scale")
            
            # Build FFmpeg command with palette
            meta = get_media_metadata(file_path)
            width = int(meta['width'] * resolution_scale)
            height = int(meta['height'] * resolution_scale)
            
            # Two-pass GIF encoding with palette
            palette_path = output_path + '.palette.png'
            
            # Pass 1: Generate palette
            (
                ffmpeg
                .input(file_path)
                .filter('fps', fps)
                .filter('scale', width, height)
                .filter('palettegen', max_colors=colors)
                .output(palette_path)
                .overwrite_output()
                .run(quiet=True)
            )
            
            # Pass 2: Apply palette
            main = ffmpeg.input(file_path).filter('fps', fps).filter('scale', width, height)
            palette = ffmpeg.input(palette_path)
            
            (
                ffmpeg
                .filter([main, palette], 'paletteuse', dither=dither.split(':')[0] if ':' in dither else dither)
                .output(output_path)
                .overwrite_output()
                .run(quiet=True)
            )
            
            # Cleanup palette
            if os.path.exists(palette_path):
                os.remove(palette_path)
                
            if os.path.exists(output_path):
                actual_size = os.path.getsize(output_path)
                actual_mb = actual_size / (1024 * 1024)
                self.status_updated.emit(f"[v2] ✓ GIF complete: {actual_mb:.2f} MB")
                return True
            return False
            
        except Exception as e:
            self.status_updated.emit(f"[v2] GIF error: {str(e)}")
            return False
