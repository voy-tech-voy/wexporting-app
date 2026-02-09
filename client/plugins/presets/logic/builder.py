"""
Presets Plugin - Command Builder

Renders executable command strings from pipeline step templates.
Injects tool executable paths from the registry into Jinja2 context.
"""
from typing import Dict, Any, List, TYPE_CHECKING

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

from .models import PipelineStep, PresetDefinition
from .exceptions import ToolNotAvailableError, CommandBuildError

if TYPE_CHECKING:
    from client.core.tool_registry.protocol import ToolRegistryProtocol


class CommandBuilder:
    """
    Renders executable command strings from pipeline step templates.
    
    Injects tool executable paths from the registry into Jinja2 context.
    Uses Jinja2 with StrictUndefined to catch missing variables early.
    
    Example:
        registry = get_registry()
        builder = CommandBuilder(registry)
        
        cmd = builder.build_command(step, {
            'input_path': 'video.mp4',
            'output_path': 'out.mp4'
        })
    """
    
    def __init__(self, registry: 'ToolRegistryProtocol'):
        """
        Initialize CommandBuilder.
        
        Args:
            registry: Tool registry for path resolution (injected, not created)
        """
        self._registry = registry
        self._jinja_env = Environment(undefined=StrictUndefined)
    
    def build_command(self, step: PipelineStep, context: Dict[str, Any]) -> str:
        """
        Render a command string for a pipeline step.
        
        The context dict is merged with the tool executable path.
        Tier 1: Basic context (input_path, output_path)
        Tier 2: + user parameters (allow_rotate, fill_method, etc.)
        Tier 3: + meta object (meta.fps, meta.is_landscape, etc.)
        
        Args:
            step: The pipeline step with command_template
            context: User inputs and file paths
            
        Returns:
            Fully resolved command string ready for subprocess execution
            
        Raises:
            ToolNotAvailableError: If the required tool is not in registry
            CommandBuildError: If template rendering fails
        """
        # Get tool executable path from registry
        tool_exe = self._registry.get_tool_path(step.tool)
        if not tool_exe:
            raise ToolNotAvailableError(step.tool)
        
        # Build Jinja2 context with tool path
        import sys
        render_context = {
            'tool_exe': tool_exe,
            'python_exe': sys.executable,
            'ffmpeg_path': self._registry.get_tool_path('ffmpeg'),  # Always available for presets
            **context
        }
        
        try:
            template = self._jinja_env.from_string(step.command_template)
            rendered = template.render(render_context)
            
            # Clean up whitespace (multi-line templates often have extra newlines)
            return self._clean_command(rendered)
            
        except TemplateSyntaxError as e:
            raise CommandBuildError(step.description, f"Template syntax error: {e}")
        except UndefinedError as e:
            raise CommandBuildError(step.description, f"Missing variable: {e}")
        except Exception as e:
            raise CommandBuildError(step.description, str(e))
    
    def build_pipeline(
        self, 
        preset: PresetDefinition, 
        context: Dict[str, Any]
    ) -> List[str]:
        """
        Build all commands for a preset's pipeline.
        
        Args:
            preset: The preset definition
            context: User inputs and file paths
            
        Returns:
            List of command strings for each pipeline step
            
        Raises:
            ToolNotAvailableError: If any required tool is not available
            CommandBuildError: If any template rendering fails
        """
        commands = []
        
        for step in preset.pipeline:
            cmd = self.build_command(step, context)
            commands.append(cmd)
        
        return commands
    
    def _clean_command(self, command: str) -> str:
        """
        Clean up rendered command string.
        
        - Collapse multiple spaces/newlines
        - Trim leading/trailing whitespace
        - Preserve quoted strings
        """
        # Replace newlines with spaces
        cleaned = command.replace('\n', ' ').replace('\r', '')
        
        # Collapse multiple spaces (but not inside quotes)
        # Simple approach: collapse runs of spaces
        import re
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        
        return cleaned.strip()
    
    def render_filename_suffix(
        self, 
        step: PipelineStep, 
        context: Dict[str, Any]
    ) -> str:
        """
        Render the filename suffix template for a step.
        
        Used for generating output filenames based on parameters.
        
        Args:
            step: Pipeline step with filename_suffix template
            context: Variables for rendering
            
        Returns:
            Rendered suffix string (e.g., "_rot_30fps")
        """
        if not step.filename_suffix:
            return ""
        
        try:
            template = self._jinja_env.from_string(step.filename_suffix)
            return template.render(context)
        except Exception:
            return ""  # Fall back to no suffix on error
