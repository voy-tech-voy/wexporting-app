"""
Suffix and path management for file generation.
Handles creation of descriptive filenames based on conversion parameters.
"""
import os
from pathlib import Path
from typing import Dict, List, Optional
from client.core.ffmpeg_utils import get_video_dimensions, ensure_output_directory_exists
from client.core.dimension_utils import calculate_target_dimensions, format_dimension_suffix

def _resolve_output_dir(params: Dict, input_path: Path) -> Path:
    """Resolve output directory honoring custom path or nested option."""
    output_dir = params.get('output_dir', '')
    use_nested = params.get('use_nested_output', False)
    nested_name = params.get('nested_output_name', 'output')
    
    # If custom output directory is set, use it
    if output_dir and os.path.isdir(output_dir):
        base_dir = Path(output_dir)
        # If both custom dir AND nested output are checked, append nested folder
        if use_nested:
            base_dir = base_dir / nested_name
    else:
        # Default to source directory
        base_dir = input_path.parent
        if use_nested:
            base_dir = base_dir / nested_name
            
    return base_dir

class SuffixManager:
    """Manages generation of output paths and suffixes for converted files."""
    
    @staticmethod
    def get_output_path(file_path: str, params: Dict, format_ext: str, variants: List[Dict] = None) -> str:
        """
        Generate full output path including suffixes.
        
        Args:
            file_path: Original input file path
            params: Dictionary of conversion parameters
            format_ext: Target format extension (e.g. 'gif', 'mp4')
            variants: Optional list of dicts with 'type' and 'value' for variants
                     (e.g. [{'type': 'size', 'value': '720'}, {'type': 'quality', 'value': 23}])
        """
        path = Path(file_path)
        base_dir = _resolve_output_dir(params, path)
        base_name = path.stem
        
        # Base Suffix (usually '_converted')
        suffix = params.get('suffix', '_converted')
        

        
        # Variant Suffixes
        variant_suffix = ""
        suppressed_types = []
        
        has_size_variant = False
        if variants:
            for v in variants:
                variant_type = v.get('type')
                variant_value = v.get('value')
                if variant_type and variant_value is not None:
                    # check if this is a size variant to suppress base resize suffix
                    if variant_type in ['size', 'resize']:
                        has_size_variant = True
                        suppressed_types.append('resize')
                    
                    if variant_type == 'quality':
                        suppressed_types.append('quality')
                        
                    part = SuffixManager.generate_variant_suffix(file_path, variant_type, variant_value, params)
                    variant_suffix += part
        
        # Generated Suffixes (Params)
        # Pass suppressed_types to avoid double suffixes
        generated_part = SuffixManager.generate_suffix(params, format_ext, skip_resize=has_size_variant, file_path=file_path, suppressed_types=suppressed_types)
        suffix += generated_part
        
        full_filename = f"{base_name}{suffix}{variant_suffix}.{format_ext}"
        output_path = base_dir / full_filename
        
        # Ensure dir exists
        ensure_output_directory_exists(str(base_dir))
        
        return str(output_path)

    @staticmethod
    def generate_suffix(params: Dict, format_ext: str, skip_resize: bool = False, file_path: str = None, suppressed_types: List[str] = None) -> str:
        """Generate suffix string based on params (Rotation, Resize, Loop, Quality)."""
        parts = []
        p = params
        suppressed = suppressed_types or []
        
        # 0. Target Size Suffix (for max_size mode)
        # Check if we're in max_size mode and add the target size to the filename
        size_mode = p.get('video_size_mode') or p.get('image_size_mode') or p.get('gif_size_mode')
        if size_mode == 'max_size':
            # Get the target size in MB
            target_mb = None
            if 'video_max_size_mb' in p:
                target_mb = p['video_max_size_mb']
            elif 'image_max_size_mb' in p:
                target_mb = p['image_max_size_mb']
            elif 'gif_max_size_mb' in p:
                target_mb = p['gif_max_size_mb']
            
            if target_mb is not None:
                # Format the size nicely (remove trailing zeros)
                if target_mb >= 1:
                    size_str = f"{target_mb:.0f}MB" if target_mb == int(target_mb) else f"{target_mb:.1f}MB"
                else:
                    # For sizes < 1MB, show in KB or with decimal
                    if target_mb < 0.1:
                        size_str = f"{int(target_mb * 1024)}KB"
                    else:
                        size_str = f"{target_mb:.2f}MB".rstrip('0').rstrip('.')
                
                # Get output resolution - prefer the calculated output resolution from size estimator
                resolution_str = ""
                output_res = p.get('_output_resolution')
                if output_res and len(output_res) == 2:
                    width, height = output_res
                    if width > 0 and height > 0:
                        resolution_str = f"_{width}x{height}"
                elif file_path:
                    # Fallback: read from input file if no output resolution calculated
                    try:
                        width, height = get_video_dimensions(file_path)
                        if width > 0 and height > 0:
                            resolution_str = f"_{width}x{height}"
                    except:
                        pass  # If we can't get dimensions, just skip resolution
                
                # In dev mode, include the estimator version
                is_dev_mode = p.get('_is_dev_mode', False)
                if is_dev_mode:
                    # Get current estimator version
                    try:
                        from client.core.target_size.size_estimator_registry import get_estimator_version
                        version = get_estimator_version()
                        parts.append(f"_{version}TargetSize{size_str}{resolution_str}")
                    except:
                        # Fallback if registry not available
                        parts.append(f"_TargetSize{size_str}{resolution_str}")
                else:
                    parts.append(f"_TargetSize{size_str}{resolution_str}")
        
        # 1. Resize Suffixes
        if not skip_resize:
            # Check 'current_resize' (Video/WebM single) or 'gif_resize_values' (GIF)
            resize_val = None
            if 'gif_resize_values' in p and p['gif_resize_values']:
                resize_val = p['gif_resize_values'][0]
            elif 'current_resize' in p:
                 resize_val = p['current_resize']
            
            if resize_val and file_path:
                # Use dimension_utils for consistent calculation
                try:
                    width, height = get_video_dimensions(file_path)
                    if width > 0 and height > 0:
                        dims = calculate_target_dimensions(file_path, str(resize_val), width, height)
                        if dims:
                            parts.append(format_dimension_suffix(dims[0], dims[1]))
                        else:
                            # Fallback to raw value if calculation fails
                            parts.append(f"_{resize_val}")
                    else:
                        parts.append(f"_{resize_val}")
                except Exception:
                    parts.append(f"_{resize_val}")
        
        # 2. Rotation Suffix (Video Tab)
        rot = p.get('rotation_angle')
        if rot and rot != 'No rotation':
             if '90' in rot: parts.append('_rot90')
             elif '180' in rot: parts.append('_rot180')
             elif '270' in rot: parts.append('_rot270')
             else: parts.append('_rot')
        
        
        # 2.5 Codec Suffix (Video Tab)
        is_gif = format_ext.lower() == 'gif' or p.get('type') == 'gif' or p.get('loop_format') == 'GIF'
        
        codec = p.get('codec')
        # Only add codec suffix for video type and when codec is specified
        if codec and not is_gif and p.get('type') == 'video':
             # Clean up codec string
             # "MP4 (H.264)" -> "H264"
             cleaned_codec = codec
             if '(' in codec:
                 cleaned_codec = codec.split('(')[1].split(')')[0]
             
             cleaned_codec = cleaned_codec.replace('.', '').replace(' ', '')
             
             if cleaned_codec:
                 parts.append(f"_codec{cleaned_codec}")
        
        # 3. GIF Specifics (FPS/Colors/Dither)
        if is_gif:
             # FPS
             if 'ffmpeg_fps' in p:
                 parts.append(f"_{p['ffmpeg_fps']}fps")
             elif 'gif_fps' in p and p.get('type') == 'loop': 
                  parts.append(f"_{p['gif_fps']}fps")
             
             # Colors
             if 'ffmpeg_colors' in p:
                 parts.append(f"_{p['ffmpeg_colors']}colors")
             elif 'colors' in p:
                 parts.append(f"_{p['colors']}colors")
            
             # Dither
             # Dither (Quality)
             dither_val = p.get('ffmpeg_dither')
             if dither_val is None:
                 dither_val = p.get('dither')
             if dither_val is None:
                 dither_val = p.get('gif_dither')
                 
             if dither_val is not None:
                 parts.append(f"_quality{dither_val}")

        # 4. Quality Suffix For Non-GIF (e.g. WebM/MP4)
        else:
             # Only if quality variants are OFF (otherwise handled by explicit variant_info)
             # AND quality is not in suppressed types
             if not p.get('multiple_qualities') and not p.get('webm_multiple_variants') and 'quality' not in suppressed:
                 q_val = None
                 if 'webm_quality' in p:
                     q_val = p['webm_quality']
                 elif 'quality' in p:
                     q_val = p['quality']
                 
                 if q_val is not None:
                      parts.append(f"_q{q_val}")
                      
        return "".join(parts)

    @staticmethod
    def generate_variant_suffix(file_path: str, variant_type: str, value, params: Dict) -> str:
        """Generate suffix for a specific variant (Size, Quality, etc)."""
        if variant_type == 'quality':
            return f"_q{value}"
            
        elif variant_type == 'size' or variant_type == 'resize':
            # Use dimension_utils for consistent calculation
            try:
                width, height = get_video_dimensions(file_path)
                if width > 0 and height > 0:
                    dims = calculate_target_dimensions(file_path, str(value), width, height)
                    if dims:
                        return format_dimension_suffix(dims[0], dims[1])
                # Fallback to raw value
                return f"_{value}"
            except Exception:
                return f"_{value}"
                
        elif variant_type == 'fps':
             return f"_{value}fps"
        elif variant_type == 'colors':
             return f"_{value}colors"
        elif variant_type == 'dither':
             return f"_d{value}"
             
        return f"_{value}"
