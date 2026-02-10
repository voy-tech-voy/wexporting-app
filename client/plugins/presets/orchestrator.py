"""
Presets Plugin - Orchestrator

Entry point that connects the logic layer with the UI layer.
Receives ToolRegistryProtocol via Dependency Injection.
"""
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QObject, pyqtSignal

from client.plugins.presets.logic import PresetManager, CommandBuilder, PresetDefinition, MediaAnalyzer, CustomPresetGenerator
from client.plugins.presets.ui import PresetGallery, ParameterForm
from client.utils.gpu_detector import get_gpu_detector

if TYPE_CHECKING:
    from client.core.tool_registry.protocol import ToolRegistryProtocol
    from client.plugins.presets.engine import PresetConversionEngine


class PresetOrchestrator(QObject):
    """
    Controller connecting preset logic with UI.
    
    Responsible for:
    - Loading presets via PresetManager
    - Displaying gallery via PresetGallery
    - Building commands via CommandBuilder when preset is selected
    - Analyzing media via MediaAnalyzer for smart presets
    - Executing conversions via async PresetConversionEngine
    
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
    go_to_lab_requested = pyqtSignal(dict)  # lab_mode_settings
    
    def __init__(self, registry: 'ToolRegistryProtocol', parent_widget: QWidget, conversion_conductor=None):
        """
        Initialize the orchestrator.
        
        Args:
            registry: Tool registry for validation and path resolution (injected)
            parent_widget: Widget to parent the gallery overlay to
            conversion_conductor: ConversionConductor for lab mode preset execution (optional)
        """
        super().__init__(parent_widget)
        
        self._registry = registry
        self._parent_widget = parent_widget
        self._conversion_conductor = conversion_conductor
        
        # Initialize logic components
        gpu_detector = get_gpu_detector()
        self._manager = PresetManager(registry, gpu_detector=gpu_detector)
        self._builder = CommandBuilder(registry)
        self._analyzer = MediaAnalyzer(registry)
        self._custom_preset_generator = CustomPresetGenerator()
        
        # Initialize UI
        self._gallery = PresetGallery(parent_widget)
        self._gallery.preset_selected.connect(self._on_preset_selected)
        self._gallery.dismissed.connect(self._on_gallery_dismissed)
        self._gallery.go_to_lab_requested.connect(self._on_go_to_lab)
        
        # Parameter form (created lazily per preset)
        self._parameter_form: Optional[ParameterForm] = None
        self._selected_preset: Optional[PresetDefinition] = None
        
        # Async conversion engine
        self._conversion_engine: Optional['PresetConversionEngine'] = None
        
        # Load presets
        self._presets: List[PresetDefinition] = []
        self.reload_presets()
    
    def reload_presets(self):
        """Load/reload all presets from disk."""
        self._presets = self._manager.load_all()
        self._gallery.set_presets(self._presets)
        print(f"[PresetOrchestrator] Loaded {len(self._presets)} presets")
    
    
    def start_conversion(self, files: List[str], output_mode: str = "source", 
                       organized_name: str = "output", custom_path: str = None):
        """
        Start async conversion using the selected preset.
        
        This method creates a PresetConversionEngine and starts it in a background thread,
        preventing UI freezes during long operations.
        
        Args:
            files: List of input file paths
            output_mode: "source", "organized", or "custom"
            organized_name: Folder name for organized mode
            custom_path: Path for custom mode
        """
        if not files:
            print("[PresetOrchestrator] No files to convert")
            return
        
        preset = self._selected_preset
        if not preset:
            print("[PresetOrchestrator] No preset selected")
            return
        
        # Check if this is a Lab Mode reference preset
        execution_mode = preset.raw_yaml.get('meta', {}).get('execution_mode')
        if execution_mode == 'lab_mode_reference':
            print(f"[PresetOrchestrator] Executing Lab Mode reference preset: {preset.name}")
            self._execute_lab_mode_preset(files, output_mode, organized_name, custom_path)
            return
        
        # Stop any existing conversion
        if self._conversion_engine and self._conversion_engine.isRunning():
            print("[PresetOrchestrator] Stopping existing conversion")
            self._conversion_engine.stop_conversion()
            self._conversion_engine.wait()
        
        print(f"[PresetOrchestrator] Starting async conversion with preset: {preset.name}")
        print(f"[PresetOrchestrator] Processing {len(files)} file(s)")
        
        # Create engine with params
        from client.plugins.presets.engine import PresetConversionEngine
        
        params = {
            'output_mode': output_mode,
            'organized_name': organized_name,
            'custom_path': custom_path,
        }
        
        self._conversion_engine = PresetConversionEngine(files, params, self)
        
        # Connect engine signals to orchestrator signals
        self._conversion_engine.progress_updated.connect(self._on_engine_progress)
        self._conversion_engine.status_updated.connect(self._on_engine_status)
        self._conversion_engine.file_completed.connect(self._on_engine_file_completed)
        self._conversion_engine.conversion_completed.connect(self._on_engine_completed)
        
        # Emit started signal
        self.conversion_started.emit()
        
        # Start engine thread
        self._conversion_engine.start()
    
    def _execute_lab_mode_preset(self, files: List[str], output_mode: str, 
                                  organized_name: str, custom_path: str):
        """
        Execute a Lab Mode reference preset - delegates to ConversionConductor.
        
        Args:
            files: List of input file paths
            output_mode: Output directory mode
            organized_name: Folder name for organized mode
            custom_path: Path for custom mode
        """
        preset = self._selected_preset
        lab_settings = preset.raw_yaml.get('lab_mode_settings', {})
        
        if not lab_settings:
            print("[PresetOrchestrator] Error: Lab Mode settings not found in preset")
            return
        
        # Delegate to ConversionConductor if available
        if self._conversion_conductor:
            print(f"[PresetOrchestrator] Delegating Lab Mode preset to ConversionConductor")
            self._conversion_conductor.start_preset_conversion_with_settings(
                files, lab_settings, output_mode, organized_name, custom_path
            )
            # Emit started signal for UI consistency
            self.conversion_started.emit()
        else:
            print("[PresetOrchestrator] Warning: No ConversionConductor available, cannot execute Lab Mode preset")
            print("[PresetOrchestrator] This preset requires Lab Mode execution support")
    
    def stop_conversion(self):
        """
        Stop the current conversion immediately.
        
        This method can be called from the UI to cancel an ongoing conversion.
        The engine will kill any running subprocess and stop processing files.
        """
        if self._conversion_engine and self._conversion_engine.isRunning():
            print("[PresetOrchestrator] Stopping conversion...")
            self._conversion_engine.stop_conversion()
    
    def _on_engine_progress(self, progress_pct: int):
        """Forward engine progress to orchestrator signals."""
        # Calculate current file index from progress
        # This is approximate since engine tracks overall progress
        total_files = len(self._conversion_engine.files) if self._conversion_engine else 1
        current_file = int((progress_pct / 100.0) * total_files)
        
        # Emit legacy progress signal
        self.conversion_progress.emit(current_file, total_files, f"Processing file {current_file}/{total_files}")
    
    def _on_engine_status(self, message: str):
        """Forward engine status updates."""
        # Status updates are handled by MainWindow, no need to forward
        pass
    
    def _on_engine_file_completed(self, source_path: str, output_path: str):
        """Handle file completion from engine."""
        # File completion is handled by MainWindow, no need to forward
        pass
    
    def _on_engine_completed(self, successful: int, failed: int, skipped: int, stopped: int):
        """Handle conversion completion from engine."""
        total = successful + failed + skipped + stopped
        
        # Emit NEW unified signal
        self.conversion_completed.emit(successful, failed, skipped, stopped)
        
        # Emit LEGACY signal for backward compatibility
        message = f"Preset conversion complete: {successful}/{total} files"
        self.conversion_finished.emit(successful == total, message)
        
        print(f"[PresetOrchestrator] Conversion completed: {successful} success, {failed} failed, {stopped} stopped")
    
    # LEGACY: Keep run_conversion for backward compatibility (redirects to start_conversion)
    def run_conversion(self, files: List[str], output_mode: str = "source", 
                       organized_name: str = "output", custom_path: str = None) -> tuple:
        """
        DEPRECATED: Use start_conversion() instead.
        
        This method is kept for backward compatibility but now delegates to
        the async start_conversion() method.
        
        Returns:
            Tuple of (0, 0) - actual results come via signals
        """
        print("[PresetOrchestrator] WARNING: run_conversion() is deprecated, use start_conversion()")
        self.start_conversion(files, output_mode, organized_name, custom_path)
        return (0, 0)  # Results come via signals
    
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
    
    def _on_go_to_lab(self, lab_settings: dict):
        """Forward go to lab request from gallery."""
        print(f"[PresetOrchestrator] Go to Lab requested with {len(lab_settings)} settings")
        self.go_to_lab_requested.emit(lab_settings)
    
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
    
    def create_custom_preset(self, lab_params: Dict[str, Any], preset_name: str) -> bool:
        """
        Create a custom preset from Lab Mode parameters.
        
        Args:
            lab_params: Parameters from CommandPanel.get_conversion_params()
            preset_name: User-provided name for the preset
            
        Returns:
            True if preset was created successfully, False otherwise
        """
        try:
            # Generate preset YAML file
            filepath = self._custom_preset_generator.generate_from_lab_params(lab_params, preset_name)
            print(f"[PresetOrchestrator] Custom preset created: {filepath}")
            
            # Reload presets to include the new one
            self.reload_presets()
            
            return True
        except Exception as e:
            print(f"[PresetOrchestrator] Failed to create custom preset: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_theme(self, is_dark: bool):
        """Update theme for gallery and all preset components."""
        self._gallery.update_theme(is_dark)

