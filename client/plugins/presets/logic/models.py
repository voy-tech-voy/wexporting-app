"""
Presets Plugin - Data Models

Defines dataclasses for preset definitions with future-proof design
to accommodate Parameters (Tier 2) and Media Analysis (Tier 3).
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class PresetStatus(Enum):
    """Preset availability status based on tool validation"""
    READY = "ready"              # All required tools available
    MISSING_TOOL = "missing"     # One or more tools not found
    INVALID = "invalid"          # YAML parse error or schema violation


class ParameterType(Enum):
    """UI control types for preset parameters (Tier 2)"""
    TOGGLE = "toggle"
    SEGMENTED_PILL = "segmented_pill"
    SLIDER = "slider"
    DROPDOWN = "dropdown"
    TEXT = "text"


@dataclass
class ParameterDefinition:
    """
    User-configurable parameter definition (Tier 2 - loaded but not rendered in Phase 1).
    
    These define the dynamic UI controls shown when a preset is selected.
    """
    id: str
    type: ParameterType
    label: str
    default: Any
    options: List[str] = field(default_factory=list)  # For dropdown/segmented
    tooltip: str = ""
    visibility_rule: str = ""  # Jinja2 expression for conditional display
    min_value: Optional[float] = None  # For sliders
    max_value: Optional[float] = None


@dataclass
class PipelineStep:
    """
    Single step in a conversion pipeline.
    
    Attributes:
        tool: Tool ID matching ToolRegistry (e.g., "ffmpeg")
        command_template: Jinja2 template string for the command
        description: Human-readable description of what this step does
        filename_suffix: Optional Jinja2 template for output naming
    """
    tool: str
    command_template: str
    description: str = ""
    filename_suffix: str = ""


@dataclass
class PresetStyle:
    """Visual styling hints for preset cards"""
    accent_color: str = "#00E0FF"
    icon: str = "default"
    glow_strength: str = "normal"


@dataclass
class PresetConstraints:
    """Input validation rules for preset"""
    accepted_types: List[str] = field(default_factory=lambda: ["video", "image"])
    accepted_extensions: List[str] = field(default_factory=list)
    min_duration: Optional[float] = None
    max_duration: Optional[float] = None
    requires_gpu: bool = False  # NEW: Indicates GPU acceleration is required


@dataclass
class PresetDefinition:
    """
    Complete preset definition loaded from YAML.
    
    Supports all complexity tiers:
    - Tier 1 (Core): id, name, category, pipeline, style
    - Tier 2 (Parameters): parameters, constraints, visibility_rule
    - Tier 3 (Media Analysis): Uses meta.* in templates (context injection)
    """
    # Core identification (Tier 1)
    id: str
    name: str
    category: str
    pipeline: List[PipelineStep]
    
    # Validation status
    status: PresetStatus = PresetStatus.READY
    missing_tools: List[str] = field(default_factory=list)
    
    # Display info (Tier 1)
    style: PresetStyle = field(default_factory=PresetStyle)
    description: str = ""
    version: str = "1.0"
    
    # Dynamic parameters (Tier 2 - loaded but not used in Phase 1)
    parameters: List[ParameterDefinition] = field(default_factory=list)
    
    # Input constraints (Tier 2)
    constraints: PresetConstraints = field(default_factory=PresetConstraints)
    
    # Social media grouping - ratio for 2-step selection (e.g., "9x16", "1x1")
    ratio: Optional[str] = None
    
    # Raw YAML for debugging/extension
    raw_yaml: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_available(self) -> bool:
        """Check if preset can be used (all tools present)"""
        return self.status == PresetStatus.READY
    
    @property
    def subtitle(self) -> str:
        """Generate subtitle for card display"""
        # Can be overridden by YAML, defaults to tool list
        if 'subtitle' in self.raw_yaml.get('meta', {}):
            return self.raw_yaml['meta']['subtitle']
        if 'subtitle' in self.raw_yaml.get('style', {}):
            return self.raw_yaml['style']['subtitle']
        return self.description[:30] if self.description else ""
