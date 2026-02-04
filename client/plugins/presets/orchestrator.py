"""
Presets Plugin - Orchestrator

Entry point that connects the logic layer with the UI layer.
Receives ToolRegistryProtocol via Dependency Injection.
"""
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QObject, pyqtSignal

from client.plugins.presets.logic import PresetManager, CommandBuilder, PresetDefinition, MediaAnalyzer
from client.plugins.presets.ui import PresetGallery, ParameterForm

if TYPE_CHECKING:
    from client.core.tool_registry.protocol import ToolRegistryProtocol


class PresetOrchestrator(QObject):
    """
    Controller connecting preset logic with UI.
    
    Responsible for:
    - Loading presets via PresetManager
    - Displaying gallery via PresetGallery
    - Building commands via CommandBuilder when preset is selected
    - Analyzing media via MediaAnalyzer for smart presets
    - Executing conversions via run_conversion()
    
    Signals:
        preset_selected: Emitted when user selects a preset (PresetDefinition)
        gallery_dismissed: Emitted when gallery is dismissed without selection
        conversion_started: Emitted when conversion begins
        conversion_progress: Emitted with (current, total, message) during conversion
        conversion_finished: Emitted with (success, message) when conversion completes
    """
    
    preset_selected = pyqtSignal(object)  # PresetDefinition
    gallery_dismissed = pyqtSignal()
    conversion_started = pyqtSignal()
    conversion_progress = pyqtSignal(int, int, str)  # current, total, message
    conversion_finished = pyqtSignal(bool, str)  # success, message - LEGACY
    conversion_completed = pyqtSignal(int, int, int, int)  # successful, failed, skipped, stopped - NEW
    
    def __init__(self, registry: 'ToolRegistryProtocol', parent_widget: QWidget):
        """
        Initialize the orchestrator.
        
        Args:
            registry: Tool registry for validation and path resolution (injected)
            parent_widget: Widget to parent the gallery overlay to
        """
        super().__init__(parent_widget)
        
        self._registry = registry
        self._parent_widget = parent_widget
        
        # Initialize logic components
        self._manager = PresetManager(registry)
        self._builder = CommandBuilder(registry)
        self._analyzer = MediaAnalyzer(registry)
        
        # Initialize UI
        self._gallery = PresetGallery(parent_widget)
        self._gallery.preset_selected.connect(self._on_preset_selected)
        self._gallery.dismissed.connect(self._on_gallery_dismissed)
        
        # Parameter form (created lazily per preset)
        self._parameter_form: Optional[ParameterForm] = None
        self._selected_preset: Optional[PresetDefinition] = None
        
        # Load presets
        self._presets: List[PresetDefinition] = []
        self.reload_presets()
    
    def reload_presets(self):
        """Load/reload all presets from disk."""
        self._presets = self._manager.load_all()
        self._gallery.set_presets(self._presets)
        print(f"[PresetOrchestrator] Loaded {len(self._presets)} presets")
    
    def run_conversion(self, files: List[str], output_mode: str = "source", 
                       organized_name: str = "output", custom_path: str = None) -> tuple:
        """
        Execute conversion using the selected preset.
        
        This method encapsulates all subprocess and file path logic,
        keeping MainWindow clean of business logic.
        
        Args:
            files: List of input file paths
            output_mode: "source", "organized", or "custom"
            organized_name: Folder name for organized mode
            custom_path: Path for custom mode
            
        Returns:
            Tuple of (success_count, total_count)
        """
        import subprocess
        import os
        from pathlib import Path
        
        if not files:
            return (0, 0)
        
        preset = self._selected_preset
        if not preset:
            print("[PresetOrchestrator] No preset selected")
            return (0, 0)
        
        print(f"[PresetOrchestrator] Starting conversion with preset: {preset.name}")
        print(f"[PresetOrchestrator] Processing {len(files)} file(s)")
        
        self.conversion_started.emit()
        
        total_files = len(files)
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i, input_path in enumerate(files):
            try:
                input_p = Path(input_path)
                
                # Determine output directory
                if output_mode == "source":
                    output_dir = input_p.parent
                elif output_mode == "organized":
                    output_dir = input_p.parent / organized_name
                    output_dir.mkdir(exist_ok=True)
                elif output_mode == "custom" and custom_path:
                    output_dir = Path(custom_path)
                    output_dir.mkdir(exist_ok=True)
                else:
                    output_dir = input_p.parent
                
                output_path = output_dir / f"{input_p.stem}_preset{input_p.suffix}"
                
                # Analyze media for smart presets
                meta = self.analyze_file(str(input_path))
                print(f"[PresetOrchestrator] Meta: fps={meta.get('fps')}, landscape={meta.get('is_landscape')}")
                
                # Get parameter values
                param_values = self.get_parameter_values()
                print(f"[PresetOrchestrator] Params: {param_values}")
                
                # Build context for template
                context = {
                    'input_path': str(input_path),
                    'output_path': str(output_path),
                    'output_path_no_ext': str(output_dir / input_p.stem),
                    'meta': meta,
                    **param_values,
                }
                
                # Build and execute command
                if preset.pipeline:
                    cmd = self._builder.build_command(preset.pipeline[0], context)
                    print(f"[PresetOrchestrator] Command: {cmd[:200]}...")
                    
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    
                    if result.returncode == 0:
                        success_count += 1
                        print(f"[PresetOrchestrator] [OK] Success: {input_p.name}")
                    else:
                        failed_count += 1
                        print(f"[PresetOrchestrator] [X] Failed: {input_p.name}")
                        print(f"[PresetOrchestrator] stderr: {result.stderr[:200]}")
                
                # Emit progress
                self.conversion_progress.emit(i + 1, total_files, f"Processed: {input_p.name}")
                
            except Exception as e:
                failed_count += 1
                print(f"[PresetOrchestrator] Error processing {input_path}: {e}")
        
        # Emit finished signals (both NEW unified and LEGACY)
        # NEW: Emit conversion_completed with detailed counts
        self.conversion_completed.emit(success_count, failed_count, 0, 0)  # skipped=0, stopped=0 for presets
        # LEGACY: Also emit conversion_finished for backward compatibility
        message = f"Preset conversion complete: {success_count}/{total_files} files"
        self.conversion_finished.emit(success_count == total_files, message)
        
        return (success_count, total_files)
    
    def show_gallery(self):
        """Show the preset gallery overlay."""
        # Ensure gallery fills parent
        if self._parent_widget:
            self._gallery.setGeometry(0, 0, 
                self._parent_widget.width(), 
                self._parent_widget.height())
        self._gallery.show_animated()
    
    def hide_gallery(self):
        """Hide the preset gallery overlay."""
        self._gallery.hide_animated()
    
    def is_gallery_visible(self) -> bool:
        """Check if gallery is currently visible."""
        return self._gallery.isVisible()
    
    def _on_preset_selected(self, preset: PresetDefinition):
        """Handle preset selection from gallery - gallery stays open to show parameters."""
        print(f"[PresetOrchestrator] Preset selected: {preset.name}")
        self._selected_preset = preset  # Track selected preset
        # Gallery stays open - user can adjust parameters
        # Gallery closes only on: background click, presets button, or lab button
        self.preset_selected.emit(preset)
    
    def _on_gallery_dismissed(self):
        """Handle gallery dismissal."""
        self._gallery.hide_animated()
        self.gallery_dismissed.emit()
    
    def build_commands(self, preset: PresetDefinition, context: dict) -> List[str]:
        """
        Build executable commands for a preset.
        
        Args:
            preset: The selected preset
            context: Variables for template rendering (input_path, output_path, etc.)
            
        Returns:
            List of command strings
        """
        return self._builder.build_pipeline(preset, context)
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a media file and return metadata.
        
        Args:
            file_path: Path to media file
            
        Returns:
            Dict with meta fields (fps, is_landscape, etc.)
        """
        return self._analyzer.analyze(file_path)
    
    def setup_parameter_form(self, preset: PresetDefinition, meta: Dict[str, Any] = None):
        """
        Setup or update the parameter form for a preset.
        
        Args:
            preset: The selected preset
            meta: Media metadata for visibility rules
        """
        self._selected_preset = preset
        
        if self._parameter_form is None:
            self._parameter_form = ParameterForm()
        
        self._parameter_form.set_parameters(preset.parameters, meta or {})
    
    def get_parameter_values(self) -> Dict[str, Any]:
        """
        Get current parameter values from the form.
        
        Returns:
            Dict of parameter id -> value
        """
        # Query the gallery's form (where the user actually interacts)
        if hasattr(self._gallery, '_parameter_form') and self._gallery._parameter_form:
            values = self._gallery._parameter_form.get_values()
            print(f"[Orchestrator] Got values from gallery form: {values}")
            return values
        
        # Fallback to orchestrator's own form (shouldn't be used)
        if self._parameter_form:
            return self._parameter_form.get_values()
        
        # Fall back to defaults if no form
        if self._selected_preset:
            return {p.id: p.default for p in self._selected_preset.parameters}
        
        return {}
    
    @property
    def selected_preset(self) -> Optional[PresetDefinition]:
        """Get the currently selected preset."""
        return self._selected_preset
    
    @property
    def presets(self) -> List[PresetDefinition]:
        """Get all loaded presets."""
        return self._presets
    
    @property
    def available_presets(self) -> List[PresetDefinition]:
        """Get only available presets (tools present)."""
        return [p for p in self._presets if p.is_available]
    
    @property
    def gallery(self) -> PresetGallery:
        """Get the gallery widget."""
        return self._gallery
    
    @property
    def analyzer(self) -> MediaAnalyzer:
        """Get the media analyzer."""
        return self._analyzer
    
    @property
    def parameter_form(self) -> Optional[ParameterForm]:
        """Get the parameter form widget."""
        return self._parameter_form
    
    def update_theme(self, is_dark: bool):
        """Update theme for gallery and all preset components."""
        self._gallery.update_theme(is_dark)
