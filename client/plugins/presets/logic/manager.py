"""
Presets Plugin - Preset Manager

Loads and validates preset definitions from YAML files.
Uses ToolRegistryProtocol via Dependency Injection to validate tool availability.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from .models import (
    PresetDefinition, 
    PresetStatus, 
    PipelineStep, 
    PresetStyle, 
    PresetConstraints,
    ParameterDefinition,
    ParameterType
)
from .exceptions import PresetLoadError, PresetValidationError

if TYPE_CHECKING:
    from client.core.tool_registry.protocol import ToolRegistryProtocol


class PresetManager:
    """
    Loads and validates preset definitions from YAML files.
    
    Accepts ToolRegistryProtocol via constructor (Dependency Injection).
    Validates that all required tools in pipeline steps are available.
    
    Example:
        registry = get_registry()
        manager = PresetManager(registry)
        presets = manager.load_all()
    """
    
    def __init__(self, registry: 'ToolRegistryProtocol', presets_dir: Optional[str] = None, gpu_detector=None):
        """
        Initialize PresetManager.
        
        Args:
            registry: Tool registry for validation (injected, not created)
            presets_dir: Directory containing YAML preset files (optional)
            gpu_detector: GPU detector instance for hardware validation (optional)
        """
        self._registry = registry
        self._presets_dir = presets_dir or self._get_default_presets_dir()
        self._presets: Dict[str, PresetDefinition] = {}
        self._gpu_detector = gpu_detector
        self._gpu_available = False
        
        # Detect GPU availability if detector provided
        if self._gpu_detector:
            encoders = self._gpu_detector.detect_encoders()
            self._gpu_available = any('nvenc' in e or 'qsv' in e or 'amf' in e for e in encoders)
            print(f"[PresetManager] GPU available: {self._gpu_available}")
    
    def _get_default_presets_dir(self) -> str:
        """Get the default presets directory path."""
        # Go from logic/ up to presets/assets/presets/
        plugin_dir = Path(__file__).parent.parent
        return str(plugin_dir / "assets" / "presets")
    
    def load_all(self) -> List[PresetDefinition]:
        """
        Load all preset YAML files from the presets directory.
        
        Returns:
            List of PresetDefinition objects (some may have MISSING_TOOL status)
        """
        self._presets.clear()
        presets_path = Path(self._presets_dir)
        
        if not presets_path.exists():
            print(f"[PresetManager] Presets directory not found: {presets_path}")
            return []
        
        # Scan recursively for YAML files in all subdirectories
        yaml_files = list(presets_path.glob("**/*.yaml")) + list(presets_path.glob("**/*.yml"))
        
        for yaml_file in yaml_files:
            try:
                preset = self.load_preset(str(yaml_file))
                self._presets[preset.id] = preset
            except PresetLoadError as e:
                print(f"[PresetManager] Warning: {e}")
        
        return list(self._presets.values())
    
    def load_preset(self, yaml_path: str) -> PresetDefinition:
        """
        Load a single preset from YAML file.
        
        Args:
            yaml_path: Path to the YAML file
            
        Returns:
            PresetDefinition object
            
        Raises:
            PresetLoadError: If file cannot be read or parsed
        """
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            raise PresetLoadError(yaml_path, "File not found")
        except yaml.YAMLError as e:
            raise PresetLoadError(yaml_path, f"YAML parse error: {e}")
        
        if not data:
            raise PresetLoadError(yaml_path, "Empty YAML file")
        
        try:
            preset = self._parse_yaml(data, yaml_path)
            preset = self._validate_tools(preset)
            return preset
        except KeyError as e:
            raise PresetLoadError(yaml_path, f"Missing required field: {e}")
        except Exception as e:
            raise PresetLoadError(yaml_path, str(e))
    
    def _parse_yaml(self, data: Dict, source_path: str) -> PresetDefinition:
        """Parse YAML data into PresetDefinition."""
        # Extract meta section (or use root level for simpler presets)
        meta = data.get('meta', data)
        
        # Parse pipeline steps
        pipeline_data = data.get('pipeline', [])
        pipeline = []
        for step_data in pipeline_data:
            step = PipelineStep(
                tool=step_data['tool'],
                command_template=step_data.get('command_template', ''),
                description=step_data.get('description', ''),
                filename_suffix=step_data.get('filename_suffix', '')
            )
            pipeline.append(step)
        
        # Parse style
        style_data = data.get('style', {})
        style = PresetStyle(
            accent_color=style_data.get('accent_color', '#00E0FF'),
            icon=style_data.get('icon', 'default'),
            glow_strength=style_data.get('glow_strength', 'normal')
        )
        
        # Parse constraints
        constraints_data = data.get('constraints', {})
        constraints = PresetConstraints(
            accepted_types=constraints_data.get('accepted_types', ['video', 'image']),
            accepted_extensions=constraints_data.get('accepted_extensions', []),
            min_duration=constraints_data.get('min_duration'),
            max_duration=constraints_data.get('max_duration'),
            requires_gpu=constraints_data.get('requires_gpu', False)
        )
        
        # Parse parameters (Tier 2 - loaded but not rendered in Phase 1)
        parameters = []
        for param_data in data.get('parameters', []):
            try:
                param_type = ParameterType(param_data.get('type', 'text'))
            except ValueError:
                param_type = ParameterType.TEXT
            
            param = ParameterDefinition(
                id=param_data['id'],
                type=param_type,
                label=param_data.get('label', param_data['id']),
                default=param_data.get('default'),
                options=param_data.get('options', []),
                tooltip=param_data.get('tooltip', ''),
                visibility_rule=param_data.get('visibility_rule', ''),
                min_value=param_data.get('min_value'),
                max_value=param_data.get('max_value')
            )
            parameters.append(param)
        
        return PresetDefinition(
            id=meta.get('id', Path(source_path).stem),
            name=meta.get('name', 'Unnamed Preset'),
            category=meta.get('category', 'general'),
            description=meta.get('description', ''),
            version=str(meta.get('version', '1.0')),
            pipeline=pipeline,
            style=style,
            constraints=constraints,
            parameters=parameters,
            output_extension=meta.get('output_extension'),  # Optional forced extension
            ratio=meta.get('ratio'),  # For social media 2-step selection
            raw_yaml=data
        )
    
    def _validate_tools(self, preset: PresetDefinition) -> PresetDefinition:
        """
        Validate that all tools required by the preset are available.
        Also validates GPU requirements if GPU detector is available.
        
        Uses registry.is_tool_available(tool_id) for each pipeline step.
        Sets status to MISSING_TOOL and populates missing_tools list if any fail.
        """
        missing = []
        
        for step in preset.pipeline:
            if not self._registry.is_tool_available(step.tool):
                missing.append(step.tool)
        
        # Check GPU requirement
        if preset.constraints.requires_gpu and not self._gpu_available:
            preset.status = PresetStatus.MISSING_TOOL
            preset.missing_tools = ["GPU (NVIDIA/AMD/Intel)"]
            return preset
        
        if missing:
            preset.status = PresetStatus.MISSING_TOOL
            preset.missing_tools = list(set(missing))  # Deduplicate
        else:
            preset.status = PresetStatus.READY
        
        return preset
    
    def get_preset(self, preset_id: str) -> Optional[PresetDefinition]:
        """Get a loaded preset by ID."""
        return self._presets.get(preset_id)
    
    def get_presets_by_category(self, category: str) -> List[PresetDefinition]:
        """Get all presets in a category."""
        return [p for p in self._presets.values() if p.category == category]
    
    def get_available_presets(self) -> List[PresetDefinition]:
        """Get only presets with READY status (all tools available)."""
        return [p for p in self._presets.values() if p.is_available]
    
    def get_all_categories(self) -> List[str]:
        """Get list of all unique categories."""
        return list(set(p.category for p in self._presets.values()))
    
    def reload(self) -> List[PresetDefinition]:
        """Reload all presets from disk."""
        return self.load_all()
