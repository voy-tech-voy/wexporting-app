"""
GIF Converter Module
Handles video-to-GIF conversion logic, including single and multi-variant exports.
"""
import os
import tempfile
import ffmpeg
from client.core.ffmpeg_utils import (
    get_video_duration,
    get_video_dimensions,
    clamp_resize_width,
    calculate_longer_edge_resize
)

class GifConverter:
    def __init__(self, engine):
        """
        Initialize the GIF converter.
        
        Args:
            engine: The parent ConversionEngine instance. Used for params, signals, and shared methods.
        """
        self.engine = engine

    @property
    def params(self):
        return self.engine.params

    def video_to_gif(self, file_path: str) -> bool:
        """Convert video to GIF using FFmpeg"""
        try:
            self.engine.status_updated.emit(f"Converting video to GIF: {os.path.basename(file_path)}")
            
            # Note: Max Size mode is now handled by TargetSizeConversionEngine
            # This converter only handles standard CRF-based GIF conversion

            
            # Check if GIF variants are requested
            gif_variants = self.params.get('gif_variants', {})
            gif_resize_values = self.params.get('gif_resize_values', [])
            self.engine.status_updated.emit(f"DEBUG: Video-to-GIF variants check - gif_variants: {gif_variants}, gif_resize_values: {gif_resize_values}")
            
            # Check if any variant list has actual values (not empty lists)
            has_variants = False
            if gif_variants:
                for key, value_list in gif_variants.items():
                    if value_list and len(value_list) > 0:
                        has_variants = True
                        break
            
            # Also check for resize variants
            if not has_variants and gif_resize_values and len(gif_resize_values) > 1:
                has_variants = True
                self.engine.status_updated.emit("DEBUG: Multiple resize variants detected")
            
            if has_variants:
                self.engine.status_updated.emit("Using GIF multiple variants conversion for video")
                return self._convert_video_to_gif_multiple_variants(file_path)
            else:
                # Single video-to-GIF conversion
                self.engine.status_updated.emit("Using single video-to-GIF conversion")
                return self._convert_single_video_to_gif(file_path)
            
        except Exception as e:
            self.engine.status_updated.emit(f"Video to GIF conversion error: {e}")
            return False

    def _convert_single_video_to_gif(self, file_path: str) -> bool:
        """Convert single video to GIF using FFmpeg"""
        # Set current_resize if gif_resize_values is provided
        gif_resize_values = self.params.get('gif_resize_values', [])
        if gif_resize_values and len(gif_resize_values) > 0:
            self.params['current_resize'] = gif_resize_values[0]
        
        output_path = self.engine.get_output_path(file_path, 'gif')
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Always use FFmpeg-only mode
        return self._convert_video_to_gif_ffmpeg_only(file_path, output_path)

    def _convert_video_to_gif_multiple_variants(self, file_path: str) -> bool:
        """Convert video to GIF with multiple variants using FFmpeg"""
        original_type = self.params.get('type')
        try:
            # Force type to 'gif' so get_output_path builds correct parameter suffixes
            # (fps, colors, dither, etc.)
            self.params['type'] = 'gif'
            
            gif_variants = self.params.get('gif_variants', {})
            gif_resize_values = self.params.get('gif_resize_values', [])
            
            # Get variant lists or default single values
            resize_variants = gif_resize_values if gif_resize_values else [None]
            fps_variants = gif_variants.get('fps', [None])
            colors_variants = gif_variants.get('colors', [None])
            dither_variants = gif_variants.get('dither', [None])
            
            # Filter out None values to ensure at least one iteration if lists are empty
            if not resize_variants: resize_variants = [None]
            if not fps_variants: fps_variants = [None]
            if not colors_variants: colors_variants = [None]
            if not dither_variants: dither_variants = [None]

            successful_conversions = 0
            total_combinations = len(resize_variants) * len(fps_variants) * len(colors_variants) * len(dither_variants)
            current_combination = 0
            
            self.engine.status_updated.emit(f"Starting {total_combinations} video-to-GIF variant combinations")
            
            # Store original params to restore later
            original_params = self.params.copy()
            
            for resize in resize_variants:
                if self.engine.should_stop: break
                for fps in fps_variants:
                    if self.engine.should_stop: break
                    for colors in colors_variants:
                        if self.engine.should_stop: break
                        for dither in dither_variants:
                            if self.engine.should_stop: break
                            
                            current_combination += 1
                            
                            # Update params for this variant
                            if resize:
                                self.params['gif_resize_values'] = [resize]
                                if str(resize).endswith('%'):
                                    self.params['gif_resize_mode'] = 'By ratio (percent)'
                                else:
                                    self.params['gif_resize_mode'] = 'By width (pixels)'
                            
                            if fps:
                                self.params['ffmpeg_fps'] = int(fps)
                            
                            if colors:
                                self.params['ffmpeg_colors'] = int(colors)
                                
                            if dither is not None and str(dither).strip():
                                d_val = int(dither)
                                self.params['dither'] = d_val
                                self.params['ffmpeg_dither'] = d_val
                                
                            # Generate output path
                            output_path = self.engine.get_output_path(file_path, 'gif')
                            
                            variant_desc = f"resize={resize}, fps={fps}, colors={colors}, dither={dither}"
                            self.engine.status_updated.emit(f"Processing variant {current_combination}/{total_combinations}: {variant_desc}")
                            
                            success = self._convert_video_to_gif_ffmpeg_only(file_path, output_path)
                            
                            if success:
                                successful_conversions += 1
                            
                            # Restore params for next iteration
                            # Note: we must update the dict content in place if self.params is a reference
                            # but original logic replaced reference. With separate class, better be careful.
                            # self.engine.params = original_params.copy() ? 
                            # Engine usually holds params as attribute. If run() set self.params=params, 
                            # replacing self.engine.params is safe IF usage is via self.engine.params.
                            self.engine.params = original_params.copy()
            
            if self.engine.should_stop:
                self.engine.status_updated.emit(f"Video-to-GIF variants stopped by user: {successful_conversions}/{current_combination} completed")
            else:
                self.engine.status_updated.emit(f"Video-to-GIF variants completed: {successful_conversions}/{total_combinations} successful")
            
            return successful_conversions > 0
            
        except Exception as e:
            self.engine.status_updated.emit(f"Error in video-to-GIF multiple variants conversion: {str(e)}")
            return False
        finally:
            if original_type:
                self.params['type'] = original_type

    def _convert_video_to_gif_ffmpeg_only(self, file_path: str, output_path: str) -> bool:
        """Convert video to GIF using advanced FFmpeg filters (palettegen/paletteuse)"""
        self.engine.status_updated.emit(f"Converting to GIF using FFmpeg engine: {os.path.basename(file_path)}")
        
        try:
            # Input args
            input_args = {}
            
            # Time cutting
            enable_time_cutting = self.params.get('enable_time_cutting', False)
            if enable_time_cutting:
                time_start = self.params.get('time_start')
                time_end = self.params.get('time_end')
                if time_start is not None and time_end is not None and time_start < time_end:
                    video_duration = get_video_duration(file_path)
                    if video_duration > 0:
                        start_time = time_start * video_duration
                        end_time = time_end * video_duration
                        self.engine.status_updated.emit(f"DEBUG: Applying time cutting - start: {start_time:.2f}s, end: {end_time:.2f}s")
                        input_args['ss'] = start_time
                        input_args['to'] = end_time
            
            input_stream = ffmpeg.input(file_path, **input_args)
            
            # Retime
            retime_enabled = self.params.get('retime_enabled') or self.params.get('enable_retime')
            retime_speed = self.params.get('retime_speed', 1.0)
            if retime_enabled and retime_speed and retime_speed != 1.0:
                try:
                    speed = float(retime_speed)
                    speed = max(0.1, min(3.0, speed))
                    self.engine.status_updated.emit(f"DEBUG: Applying retime at {speed:.2f}x")
                    input_stream = ffmpeg.filter(input_stream, 'setpts', f'PTS/{speed}')
                except Exception:
                    pass
            
            # FPS
            fps = self.params.get('ffmpeg_fps', 15)
            input_stream = ffmpeg.filter(input_stream, 'fps', fps=fps)
            
            # Resize
            original_width, original_height = get_video_dimensions(file_path)
            resize_mode = self.params.get('gif_resize_mode', 'No resize')
            resize_values = self.params.get('gif_resize_values', [])
            
            # Check if resize_values contains "L" prefix (longer edge format)
            has_longer_edge_prefix = resize_values and isinstance(resize_values[0], str) and resize_values[0].startswith('L')
            
            if (resize_mode != 'No resize' or has_longer_edge_prefix) and resize_values:
                resize_value = resize_values[0]
                # Check for "L" prefix first (longer edge format)
                if isinstance(resize_value, str) and resize_value.startswith('L'):
                    # Handle "L" prefix format for longer edge
                    target_longer_edge = int(resize_value[1:])
                    longer_edge = max(original_width, original_height)
                    # Don't upscale if longer edge is already smaller than target
                    if longer_edge >= target_longer_edge:
                        if original_width > original_height:
                            # Width is longer: scale by width
                            input_stream = ffmpeg.filter(input_stream, 'scale', str(target_longer_edge), '-2', flags='lanczos')
                        else:
                            # Height is longer: calculate width to maintain aspect ratio
                            ratio = target_longer_edge / original_height
                            new_w = int(original_width * ratio)
                            # Ensure even dimensions
                            new_w = new_w if new_w % 2 == 0 else new_w - 1
                            input_stream = ffmpeg.filter(input_stream, 'scale', str(new_w), str(target_longer_edge), flags='lanczos')
                elif resize_mode == 'By ratio (percent)':
                    if resize_value.endswith('%'):
                        percent = float(resize_value[:-1]) / 100.0
                        new_width = int(original_width * percent)
                        new_width = clamp_resize_width(original_width, new_width)
                        input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2', flags='lanczos')
                elif resize_mode == 'By width (pixels)':
                    new_width = int(resize_value)
                    new_width = clamp_resize_width(original_width, new_width)
                    input_stream = ffmpeg.filter(input_stream, 'scale', str(new_width), '-2', flags='lanczos')
                elif resize_mode == 'By longer edge (pixels)':
                    # Handle mode name format for longer edge
                    # Check if resize_value has 'L' prefix and strip it
                    if isinstance(resize_value, str) and resize_value.startswith('L'):
                        target_longer_edge = int(resize_value[1:])
                    else:
                        target_longer_edge = int(resize_value)
                    longer_edge = max(original_width, original_height)
                    # Don't upscale if longer edge is already smaller than target
                    if longer_edge >= target_longer_edge:
                        if original_width > original_height:
                            # Width is longer: scale by width
                            input_stream = ffmpeg.filter(input_stream, 'scale', str(target_longer_edge), '-2', flags='lanczos')
                        else:
                            # Height is longer: calculate width to maintain aspect ratio
                            ratio = target_longer_edge / original_height
                            new_w = int(original_width * ratio)
                            # Ensure even dimensions
                            new_w = new_w if new_w % 2 == 0 else new_w - 1
                            input_stream = ffmpeg.filter(input_stream, 'scale', str(new_w), str(target_longer_edge), flags='lanczos')
            
            # Apply auto-resize resolution scale (from size optimization)
            # This is applied ON TOP of user's resize choice
            resolution_scale = self.params.get('_resolution_scale')
            if resolution_scale and resolution_scale < 1.0:
                # Scale to percentage of current size
                scale_w = f'iw*{resolution_scale:.2f}'
                scale_h = f'ih*{resolution_scale:.2f}'
                self.engine.status_updated.emit(f"Applying auto-resize: {resolution_scale*100:.0f}% of current size")
                input_stream = ffmpeg.filter(input_stream, 'scale', scale_w, scale_h)
                # Ensure even dimensions
                input_stream = ffmpeg.filter(input_stream, 'scale', 'trunc(iw/2)*2', 'trunc(ih/2)*2')
            
            # Aspect Ratio Presets (GIF)
            preset_ratio = self.params.get('gif_preset_ratio')
            is_instagram = self.params.get('gif_preset_social') == 'Instagram'
            if is_instagram or preset_ratio:
                target_ratio = preset_ratio or ('9:16' if is_instagram else None)
                if target_ratio:
                    ratio_map = {
                        '4:3': (1440, 1080),
                        '1:1': (1080, 1080),
                        '16:9': (1920, 1080),
                        '9:16': (1080, 1920),
                        '3:4': (1080, 1350)
                    }
                    if target_ratio in ratio_map:
                        tw, th = ratio_map[target_ratio]
                        self.engine.status_updated.emit(f"Applying GIF preset ratio: {target_ratio} ({tw}x{th})")
                        input_stream = ffmpeg.filter(input_stream, 'scale', tw, th, force_original_aspect_ratio='decrease')
                        input_stream = ffmpeg.filter(input_stream, 'pad', tw, th, '(ow-iw)/2', '(oh-ih)/2')
            
            # Rotation
            rotation_angle = self.params.get('rotation')
            skip_rotation_for_longer_edge = (
                resize_mode == 'By longer edge (pixels)' and 
                (not rotation_angle or rotation_angle == "No rotation")
            )
            if rotation_angle and rotation_angle != "No rotation" and not skip_rotation_for_longer_edge and rotation_angle == "90° clockwise":
                input_stream = ffmpeg.filter(input_stream, 'transpose', 1)
            elif rotation_angle and rotation_angle != "No rotation" and not skip_rotation_for_longer_edge and rotation_angle == "180°":
                input_stream = ffmpeg.filter(input_stream, 'transpose', 2)
                input_stream = ffmpeg.filter(input_stream, 'transpose', 2)
            elif rotation_angle and rotation_angle != "No rotation" and not skip_rotation_for_longer_edge and rotation_angle == "270° clockwise":
                input_stream = ffmpeg.filter(input_stream, 'transpose', 2)
                
            # Blur
            if self.params.get('ffmpeg_blur', False):
                input_stream = ffmpeg.filter(input_stream, 'smartblur', lr='1.0', ls='-0.5', lt='-3.0')
            
            # Split stream for palette generation
            split = input_stream.split()
            
            # Palette generation
            colors = self.params.get('colors', 256)
            palette = split[0].filter('palettegen', max_colors=colors)
            
            # Palette use - map dither value (0-5) to FFmpeg dither algorithm
            dither_value = self.params.get('dither', 3)
            
            dither_map = {
                0: 'none',
                1: 'bayer:bayer_scale=1',
                2: 'bayer:bayer_scale=3',
                3: 'sierra2_4a',
                4: 'sierra2',
                5: 'floyd_steinberg'
            }
            
            dither = dither_map.get(dither_value, 'sierra2_4a')
            paletteuse_args = {}
            
            if dither.startswith('bayer:bayer_scale='):
                try:
                    scale = int(dither.split('=')[1])
                    paletteuse_args['dither'] = 'bayer'
                    paletteuse_args['bayer_scale'] = scale
                except:
                    paletteuse_args['dither'] = dither
            else:
                paletteuse_args['dither'] = dither
                
            final = ffmpeg.filter([split[1], palette], 'paletteuse', **paletteuse_args)
            
            # Output
            out = ffmpeg.output(final, output_path)
            if self.params.get('overwrite', False):
                out = ffmpeg.overwrite_output(out)
                
            self.engine.run_ffmpeg_with_cancellation(out, overwrite_output=True)
            
            self.engine.status_updated.emit(f"Successfully converted to GIF: {os.path.basename(output_path)}")
            self.engine.file_completed.emit(file_path, output_path)
            return True
            
        except Exception as e:
            error_msg = f"FFmpeg error: {str(e)}"
            self.engine.status_updated.emit(error_msg)
            return False

    def _convert_video_to_temp_gif(self, file_path: str, resize_variant: str = None, fps_variant: str = None) -> str:
        """Convert video to temporary GIF for variant processing"""
        try:
            temp_gif = tempfile.NamedTemporaryFile(suffix='.gif', delete=False).name
            
            # Ensure temp directory exists
            os.makedirs(os.path.dirname(temp_gif), exist_ok=True)
            
            # Handle time cutting for GIF
            input_args = {}
            enable_time_cutting = self.params.get('enable_time_cutting', False)
            if enable_time_cutting:
                time_start = self.params.get('time_start')
                time_end = self.params.get('time_end')
                if time_start is not None and time_end is not None and time_start < time_end:
                    video_duration = get_video_duration(file_path)
                    if video_duration > 0:
                        start_time = time_start * video_duration
                        end_time = time_end * video_duration
                        self.engine.status_updated.emit(f"DEBUG: Applying time cutting to temp GIF - start: {start_time:.2f}s, end: {end_time:.2f}s")
                        input_args['ss'] = start_time
                        input_args['to'] = end_time
                
            input_stream = ffmpeg.input(file_path, **input_args)

            # Apply retime
            retime_enabled = self.params.get('retime_enabled') or self.params.get('enable_retime')
            retime_speed = self.params.get('retime_speed', 1.0)
            if retime_enabled and retime_speed and retime_speed != 1.0:
                try:
                    speed = float(retime_speed)
                    speed = max(0.1, min(3.0, speed))
                    self.engine.status_updated.emit(f"DEBUG: Applying temp GIF retime at {speed:.2f}x (setpts)")
                    input_stream = ffmpeg.filter(input_stream, 'setpts', f'PTS/{speed}')
                except Exception as e:
                    self.engine.status_updated.emit(f"DEBUG: Skipping temp GIF retime due to error: {e}")
            
            # Apply FPS
            if fps_variant:
                fps = int(fps_variant)
            else:
                gif_fps = self.params.get('gif_fps', '15')
                fps = int(gif_fps) if gif_fps.isdigit() else 15
            
            # Apply size scaling
            if resize_variant:
                if resize_variant.endswith('%'):
                    percent = float(resize_variant[:-1]) / 100
                    original_width, original_height = get_video_dimensions(file_path)
                    target_w = int(original_width * percent) if original_width else None
                    if target_w:
                        target_w = clamp_resize_width(original_width, target_w)
                        target_h = int((target_w * original_height) / original_width) if original_height else -2
                        input_stream = ffmpeg.filter(input_stream, 'scale', str(target_w), str(target_h))
                    else:
                        input_stream = ffmpeg.filter(input_stream, 'scale', f"trunc(iw*{percent}/2)*2", f"trunc(ih*{percent}/2)*2")
                elif resize_variant.startswith('L'):
                    target_longer_edge = int(resize_variant[1:])
                    original_width, original_height = get_video_dimensions(file_path)
                    longer_edge = max(original_width, original_height)
                    if longer_edge >= target_longer_edge:
                        if original_width > original_height:
                            input_stream = ffmpeg.filter(input_stream, 'scale', str(target_longer_edge), '-2')
                        else:
                            ratio = target_longer_edge / original_height
                            new_w = int(original_width * ratio)
                            new_w = new_w if new_w % 2 == 0 else new_w - 1
                            input_stream = ffmpeg.filter(input_stream, 'scale', str(new_w), str(target_longer_edge))
                else:
                    width = int(resize_variant)
                    original_width, _ = get_video_dimensions(file_path)
                    width = clamp_resize_width(original_width, width)
                    input_stream = ffmpeg.filter(input_stream, 'scale', str(width), '-2')
            else:
                scale_option = self.params.get('gif_scale', 'Keep Original')
                if scale_option == '50%':
                    input_stream = ffmpeg.filter(input_stream, 'scale', 'iw/2', 'ih/2')
                elif scale_option == '25%':
                    input_stream = ffmpeg.filter(input_stream, 'scale', 'iw/4', 'ih/4')
            
            # Create GIF
            output = ffmpeg.output(input_stream, temp_gif, r=fps)
            if self.engine.should_stop:
                return None
                
            ffmpeg.run(output, quiet=True, overwrite_output=True)
            
            return temp_gif
            
        except Exception as e:
            self.engine.status_updated.emit(f"Error creating temp GIF: {e}")
            return None

    def optimize_gif(self, file_path: str) -> bool:
        """Optimize existing GIF using FFmpeg with variant support"""
        try:
            # Check if GIF variants are requested
            gif_variants = self.params.get('gif_variants', {})
            gif_resize_values = self.params.get('gif_resize_values', [])
            self.engine.status_updated.emit(f"DEBUG: GIF variants check - gif_variants: {gif_variants}, gif_resize_values: {gif_resize_values}")
            
            # Check if any variant list has actual values (not empty lists)
            has_variants = False
            if gif_variants:
                for key, value_list in gif_variants.items():
                    if value_list and len(value_list) > 0:
                        has_variants = True
                        break
            
            # Also check for resize variants
            if not has_variants and gif_resize_values and len(gif_resize_values) > 1:
                has_variants = True
                self.engine.status_updated.emit("DEBUG: Multiple resize variants detected for GIF optimization")
            
            self.engine.status_updated.emit(f"DEBUG: Has valid variants: {has_variants}")
            
            if has_variants:
                self.engine.status_updated.emit("Using GIF multiple variants conversion")
                return self._convert_gif_multiple_variants(file_path, 'gif')
            else:
                # Single GIF optimization
                self.engine.status_updated.emit("Using single GIF optimization")
                output_path = self.engine.get_output_path(file_path, 'gif')
                
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                return self._convert_video_to_gif_ffmpeg_only(file_path, output_path)
            
        except Exception as e:
            self.engine.status_updated.emit(f"GIF optimization error: {e}")
            return False

    def _convert_gif_multiple_variants(self, file_path: str, format_ext: str) -> bool:
        """Convert GIF with multiple variants for size, fps, colors using FFmpeg"""
        # Check if GIF multiple variants is enabled
        gif_multiple_variants = self.params.get('gif_multiple_variants', False)
        
        gif_variants = self.params.get('gif_variants', {})
        gif_resize_values = self.params.get('gif_resize_values', [])
        self.engine.status_updated.emit(f"Processing GIF variants: {gif_variants}, resize_values: {gif_resize_values}")
        
        # Get variant lists or default single values
        # Only use variants if gif_multiple_variants is enabled
        if gif_multiple_variants:
            size_variants = gif_resize_values if gif_resize_values else [None]
            fps_variants = gif_variants.get('fps', [])
            colors_variants = gif_variants.get('colors', [])
            dither_variants = gif_variants.get('dither', [])
        else:
            # Use single values from params
            size_variants = [None]
            fps_variants = [self.params.get('gif_fps')]
            colors_variants = [self.params.get('gif_colors')]
            dither_variants = [self.params.get('gif_dither')]
        
        # Filter out None values and empty lists to ensure at least one iteration
        if not size_variants or size_variants == [None]: size_variants = [None]
        if not fps_variants: fps_variants = [self.params.get('gif_fps', 15)]
        if not colors_variants: colors_variants = [self.params.get('gif_colors', 256)]
        if not dither_variants: dither_variants = [self.params.get('gif_dither', 50)]
        
        successful_conversions = 0
        total_combinations = len(size_variants) * len(fps_variants) * len(colors_variants) * len(dither_variants)
        current_combination = 0
        
        self.engine.status_updated.emit(f"Starting {total_combinations} GIF variant combinations")
        
        # Store original params
        original_params = self.params.copy()
        
        # Generate all combinations of variants
        for size in size_variants:
            if self.engine.should_stop: break
            for fps in fps_variants:
                if self.engine.should_stop: break
                for colors in colors_variants:
                    if self.engine.should_stop: break
                    for dither in dither_variants:
                        if self.engine.should_stop: break
                    
                        current_combination += 1
                        try:
                            # Update params for this variant
                            if size:
                                self.params['gif_resize_values'] = [size]
                                if str(size).endswith('%'):
                                    self.params['gif_resize_mode'] = 'By ratio (percent)'
                                else:
                                    self.params['gif_resize_mode'] = 'By width (pixels)'
                            
                            if fps:
                                self.params['ffmpeg_fps'] = int(fps)
                            
                            if colors:
                                self.params['ffmpeg_colors'] = int(colors)
                                
                            if dither:
                                self.params['ffmpeg_dither'] = dither

                            # Create output path with variant suffixes
                            output_path = self.engine.get_output_path(file_path, format_ext)
                            
                            # Ensure output directory exists
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            
                            variant_desc = f"size={size}, fps={fps}, colors={colors}, dither={dither}"
                            self.engine.status_updated.emit(f"Processing variant {current_combination}/{total_combinations}: {variant_desc}")
                            
                            # Convert with these parameters using FFmpeg
                            success = self._convert_video_to_gif_ffmpeg_only(file_path, output_path)
                            
                            if success:
                                successful_conversions += 1
                                self.engine.file_completed.emit(file_path, output_path)
                                self.engine.status_updated.emit(f"[OK] GIF {variant_desc} completed")
                            else:
                                self.engine.status_updated.emit(f"[X] GIF {variant_desc} failed")
                            
                            # Restore original parameters
                            self.engine.params = original_params.copy()
                                    
                        except Exception as e:
                            self.engine.status_updated.emit(f"GIF variant conversion error: {str(e)}")
        
        if self.engine.should_stop:
            self.engine.status_updated.emit(f"GIF variants conversion stopped by user: {successful_conversions}/{current_combination} completed")
        else:
            self.engine.status_updated.emit(f"GIF variants completed: {successful_conversions}/{total_combinations} successful")
        
        return successful_conversions > 0
