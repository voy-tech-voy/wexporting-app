"""
Custom Preset Generator

Converts Lab Mode parameters into YAML preset definitions.
"""
import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class CustomPresetGenerator:
    """
    Generates YAML preset files from Lab Mode parameters.
    
    Responsibilities:
    - Map Lab Mode params dict to preset YAML structure
    - Generate unique preset IDs
    - Save to user_custom_presets/ directory
    """
    
    def __init__(self, user_presets_dir: Optional[str] = None):
        """
        Initialize the generator.
        
        Args:
            user_presets_dir: Directory to save user presets (optional)
        """
        if user_presets_dir:
            self._user_presets_dir = Path(user_presets_dir)
        else:
            import os
            try:
                from client.version import APP_NAME
                app_name = APP_NAME
            except ImportError:
                app_name = "wexporting"
            self._user_presets_dir = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / app_name / "user_custom_presets"
        # Ensure directory exists
        self._user_presets_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_from_lab_params(self, params: Dict[str, Any], preset_name: str) -> str:
        """
        Generate a preset YAML file from Lab Mode parameters.
        
        Args:
            params: Parameters from CommandPanel.get_conversion_params()
            preset_name: User-provided name for the preset
            
        Returns:
            Path to the created YAML file
        """
        # Generate unique ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        preset_id = f"user_custom_{timestamp}"
        
        # All custom presets use "custom" category for filter bar
        category = "custom"
        
        # Build YAML structure with Lab Mode reference
        preset_yaml = {
            'meta': {
                'id': preset_id,
                'name': preset_name,
                'category': category,
                'description': f"Custom preset created from Lab Mode",
                'version': "1.0",
                'output_extension': params.get('output_format', '.mp4'),
                'execution_mode': 'lab_mode_reference'  # NEW: Indicates Lab Mode execution
            },
            'style': {
                'accent_color': "#9C27B0",  # Purple for custom presets
                'icon': "text:custom",
                'glow_strength': "normal"
            },
            'constraints': {
                'accepted_types': self._infer_accepted_types(params),
                'min_duration': 0.1
            },
            # NEW: Store complete Lab Mode settings for execution
            'lab_mode_settings': params.copy(),  # Store ALL Lab Mode params
            # Keep lab_mode_info for tooltip display (backward compat)
            'lab_mode_info': {
                'output_format': params.get('output_format', ''),
                'codec': params.get('codec', ''),
                'quality': params.get('quality', ''),
                'resize_mode': params.get('resize_mode', ''),
                'resize_width': params.get('resize_width', ''),
                'resize_height': params.get('resize_height', ''),
                'rotation_angle': params.get('rotation_angle', ''),
                'audio_enabled': params.get('audio_enabled', True),
                'comparison_enabled': params.get('comparison_enabled', False),
                'created_timestamp': datetime.now().isoformat()
            }
        }
        
        # Add parameters if present (for UI customization)
        parameters = self._extract_parameters(params)
        if parameters:
            preset_yaml['parameters'] = parameters
        
        # Save to file
        filename = f"{preset_id}.yaml"
        filepath = self._user_presets_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(preset_yaml, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        print(f"[CustomPresetGenerator] Created Lab Mode reference preset: {filepath}")
        return str(filepath)
    
    def _infer_category(self, params: Dict[str, Any]) -> str:
        """Infer preset category from params."""
        output_format = params.get('output_format', '').lower()
        
        if output_format in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
            return 'video'
        elif output_format in ['.gif']:
            return 'loop'
        elif output_format in ['.jpg', '.png', '.webp', '.avif']:
            return 'image'
        else:
            return 'utility'
    
    def _infer_accepted_types(self, params: Dict[str, Any]) -> list:
        """Infer accepted input types from params."""
        category = self._infer_category(params)
        
        if category == 'video':
            return ['video']
        elif category == 'loop':
            return ['video']
        elif category == 'image':
            return ['image']
        else:
            return ['video', 'image']
    
    def _build_pipeline(self, params: Dict[str, Any]) -> list:
        """
        Build pipeline steps from Lab Mode params.
        
        This is the core mapping logic that converts Lab Mode settings
        into FFmpeg/ImageMagick commands.
        """
        # Determine tool based on output format
        output_format = params.get('output_format', '.mp4')
        
        if output_format in ['.jpg', '.png', '.webp', '.avif']:
            tool = 'magick'
        else:
            tool = 'ffmpeg'
        
        # Build command template
        command_parts = []
        
        if tool == 'ffmpeg':
            command_parts.append('"{{ ffmpeg_path }}" -i "{{ input_path }}"')
            
            # Add video filters
            vf_filters = []
            
            # Resize
            if params.get('resize_enabled'):
                width = params.get('resize_width', -1)
                height = params.get('resize_height', -1)
                vf_filters.append(f'scale={width}:{height}')
            
            # Add filters
            if vf_filters:
                command_parts.append(f'-vf "{",".join(vf_filters)}"')
            
            # Codec
            codec_label = params.get('codec', 'libx264')
            codec = self._map_codec_label(codec_label)
            command_parts.append(f'-c:v {codec}')
            
            # Quality/CRF
            if 'quality' in params:
                command_parts.append(f'-crf {params["quality"]}')
            
            # Audio
            if params.get('audio_enabled', True):
                command_parts.append('-c:a aac')
            else:
                command_parts.append('-an')
            
            command_parts.append('"{{ output_path }}"')
        
        else:  # ImageMagick
            command_parts.append('"{{ magick_path }}" "{{ input_path }}"')
            
            # Resize
            if params.get('resize_enabled'):
                width = params.get('resize_width', '')
                height = params.get('resize_height', '')
                command_parts.append(f'-resize {width}x{height}')
            
            # Quality
            if 'quality' in params:
                command_parts.append(f'-quality {params["quality"]}')
            
            command_parts.append('"{{ output_path }}"')
        
        command_template = ' '.join(command_parts)
        
        return [{
            'tool': tool,
            'description': "Custom conversion",
            'filename_suffix': "",
            'command_template': command_template
        }]
    
    def _map_codec_label(self, codec_label: str) -> str:
        """
        Map UI codec labels to actual FFmpeg codec values.
        
        Args:
            codec_label: Display label from UI (e.g., "MP4 (H.264)")
            
        Returns:
            Actual codec value for FFmpeg (e.g., "libx264")
        """
        codec_map = {
            # Video codecs
            "MP4 (H.264)": "libx264",
            "MP4 (H.265/HEVC)": "libx265",
            "WebM (VP9)": "libvpx-vp9",
            "WebM (AV1)": "libsvtav1",
            "ProRes": "prores_ks",
            "DNxHD": "dnxhd",
            # Add more mappings as needed
        }
        
        # Return mapped value or original if not found
        return codec_map.get(codec_label, codec_label)
    
    def _extract_parameters(self, params: Dict[str, Any]) -> list:
        """
        Extract dynamic parameters that should be exposed in the UI.
        
        For now, we'll keep it simple and not expose parameters.
        Future enhancement: Allow users to mark certain params as "adjustable".
        """
        return []
