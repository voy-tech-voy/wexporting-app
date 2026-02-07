"""
Conversion Conductor - Mediator-Shell Architecture

Extracted from MainWindow to handle conversion lifecycle management.
Coordinates conversion engines, progress tracking, and UI updates.
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class ConversionConductor(QObject):
    """
    Conductor for conversion lifecycle management.
    
    Responsibilities:
    - Own and manage ConversionEngine instances
    - Start/stop conversions (Manual, Target Size, Preset modes)
    - Connect engine signals to UI components
    - Track progress via ConversionProgressManager
    - Handle conversion completion and UI reset
    
    This class follows the Mediator-Shell pattern: it coordinates
    conversion logic without MainWindow needing to know engine details.
    """
    
    # Signals
    status_updated = pyqtSignal(str)  # Forward status messages
    
    def __init__(self,
                 drag_drop_area,
                 command_panel,
                 output_footer,
                 progress_manager,
                 dialogs,
                 update_status_callback):
        """
        Initialize the ConversionConductor.
        
        Args:
            drag_drop_area: DragDropArea component (file list)
            command_panel: CommandPanel component (parameters)
            output_footer: OutputFooter component (progress bars, start/stop)
            progress_manager: ConversionProgressManager (progress tracking)
            dialogs: DialogManager (warnings, errors)
            update_status_callback: Callable for status bar updates
        """
        super().__init__()
        
        # Store component references
        self.drag_drop_area = drag_drop_area
        self.command_panel = command_panel
        self.output_footer = output_footer
        self.progress_manager = progress_manager
        self.dialogs = dialogs
        self.update_status = update_status_callback
        
        # State
        self.conversion_engine = None
        self._active_preset = None
        self._completed_files_count = 0
    
    def set_active_preset(self, preset):
        """Set the active preset (called by MainWindow when preset is applied)."""
        self._active_preset = preset
    
    def clear_active_preset(self):
        """Clear the active preset (called when switching modes)."""
        self._active_preset = None
    
    def start_conversion(self, params):
        """
        Start the conversion process.
        
        Validates preconditions, creates appropriate engine, and starts conversion.
        Parameter gathering is done by CommandPanel.
        
        Args:
            params: Conversion parameters from CommandPanel
        """
        files = self.drag_drop_area.get_files()
        
        if not files:
            self.dialogs.show_warning("No Files", "Please add files for conversion first.")
            return
            
        if self.conversion_engine and self.conversion_engine.isRunning():
            self.dialogs.show_warning("Conversion Running", "A conversion is already in progress.")
            return
        
        # Update UI state
        self.output_footer.set_converting(True)
        
        # Check if we should use TargetSizeConversionEngine (max_size mode with any estimator version)
        use_target_size_engine = False
        size_mode = params.get('video_size_mode') or params.get('image_size_mode') or params.get('gif_size_mode')
        
        if size_mode == 'max_size':
            # Get version from params (UI selection), fall back to global version
            ui_version = params.get('estimator_version')
            from client.core.target_size.size_estimator_registry import get_estimator_version
            current_version = ui_version or get_estimator_version()
            use_target_size_engine = True
            print(f"[ConversionConductor] Using TargetSizeConversionEngine (estimator version: {current_version})")
        
        # Calculate totals with progress manager for accurate progress tracking
        self._calculate_conversion_totals(files, params)
        
        # Create appropriate engine
        if use_target_size_engine:
            from client.core.target_size import TargetSizeConversionEngine
            self.conversion_engine = TargetSizeConversionEngine(files, params, self.progress_manager)
            print(f"[ConversionConductor] Using TargetSizeConversionEngine")
        else:
            # Use modular manual mode engine
            from client.core.manual_mode import ManualModeConversionEngine
            self.conversion_engine = ManualModeConversionEngine(files, params, self.progress_manager)
            print(f"[ConversionConductor] Using ManualModeConversionEngine")
        
        # Connect engine signals
        self.conversion_engine.progress_updated.connect(self.set_progress)
        self.conversion_engine.file_progress_updated.connect(self.on_file_progress)
        self.conversion_engine.status_updated.connect(self.update_status)
        self.conversion_engine.file_completed.connect(self.on_file_completed)
        
        # Handle different signal names between engines
        # NEW: Connect to unified conversion_completed signal if available
        if hasattr(self.conversion_engine, 'conversion_completed'):
            self.conversion_engine.conversion_completed.connect(self._on_conversion_completed)
        # LEGACY: Only connect to old conversion_finished if new signal doesn't exist
        elif hasattr(self.conversion_engine, 'conversion_finished'):
            self.conversion_engine.conversion_finished.connect(self.on_conversion_finished)
        
        # Reset progress bars in output footer
        self.output_footer.reset_progress()
            
        # Start conversion
        self.set_progress(0)
        self.update_status("Starting conversion...")
        self.conversion_engine.start()
    
    def start_preset_conversion(self):
        """
        Execute conversion using the active preset - delegates to PresetOrchestrator.
        
        Collects parameters from UI components and routes the request to the orchestrator,
        which handles all business logic.
        """
        files = self.drag_drop_area.get_files()
        if not files:
            self.dialogs.show_warning("No Files", "Please add files for conversion first.")
            return
        
        # Get orchestrator (owns the conversion logic)
        if not hasattr(self.drag_drop_area, '_preset_orchestrator'):
            self.dialogs.show_error("Error", "Preset orchestrator not available.")
            return
        
        orchestrator = self.drag_drop_area._preset_orchestrator
        
        # Collect output settings from footer (UI → Data)
        output_mode = self.output_footer.get_output_mode()
        organized_name = self.output_footer.get_organized_name() or "output"
        custom_path = self.output_footer.get_custom_path()
        
        # Update UI state (show converting)
        self.output_footer.set_converting(True)
        self.output_footer.reset_progress()
        
        preset_name = self._active_preset.name if self._active_preset else "Unknown"
        self.update_status(f"Converting with preset: {preset_name}")
        
        # Wire up progress signals from orchestrator's engine
        def on_progress(current, total, message):
            progress = int(current / total * 100) if total > 0 else 0
            self.set_progress(progress)
            self.update_status(message)
        
        def on_status(message):
            """Forward status updates from engine."""
            self.update_status(message)
        
        def on_file_progress(file_index, progress):
            """Forward file progress from engine."""
            self.on_file_progress(file_index, progress)
        
        def on_file_completed(source_path, output_path):
            """Forward file completion from engine."""
            self.on_file_completed(source_path, output_path)
        
        def on_completed(successful, failed, skipped, stopped):
            """Handle unified completion signal from engine."""
            self.progress_manager.reset()
            self._reset_conversion_ui()
            self.drag_drop_area.show_conversion_toast(successful, failed, skipped, stopped)
            
            # Disconnect signals after completion
            try:
                if orchestrator._conversion_engine:
                    orchestrator._conversion_engine.status_updated.disconnect(on_status)
                    orchestrator._conversion_engine.file_progress_updated.disconnect(on_file_progress)
                    orchestrator._conversion_engine.file_completed.disconnect(on_file_completed)
                orchestrator.conversion_progress.disconnect(on_progress)
                orchestrator.conversion_completed.disconnect(on_completed)
            except TypeError:
                pass  # Already disconnected
        
        # Connect signals to engine (via orchestrator)
        orchestrator.conversion_progress.connect(on_progress)
        orchestrator.conversion_completed.connect(on_completed)
        
        # Connect directly to engine signals for real-time updates
        # Note: We connect after start_conversion creates the engine
        def connect_engine_signals():
            if orchestrator._conversion_engine:
                orchestrator._conversion_engine.status_updated.connect(on_status)
                orchestrator._conversion_engine.file_progress_updated.connect(on_file_progress)
                orchestrator._conversion_engine.file_completed.connect(on_file_completed)
        
        # Delegate execution to orchestrator (async, non-blocking)
        orchestrator.start_conversion(
            files=files,
            output_mode=output_mode,
            organized_name=organized_name,
            custom_path=custom_path
        )
        
        # Connect engine signals after engine is created
        connect_engine_signals()
    
    def stop_conversion(self):
        """Stop the current conversion process."""
        # Stop regular conversion engine
        if self.conversion_engine and self.conversion_engine.isRunning():
            self.update_status("Stopping conversion...")
            self.conversion_engine.stop_conversion()
            # The button state will be reset in on_conversion_finished
        
        # Also stop preset engine if running
        if hasattr(self.drag_drop_area, '_preset_orchestrator'):
            orchestrator = self.drag_drop_area._preset_orchestrator
            if hasattr(orchestrator, 'stop_conversion'):
                orchestrator.stop_conversion()
    
    def _calculate_conversion_totals(self, files, params):
        """
        Calculate total outputs using ConversionProgressManager.
        Delegates all param extraction to manager for cleaner conductor.
        """
        try:
            result = self.progress_manager.calculate_from_params(files, params)
            print(f"[ProgressManager] Valid: {result.valid_count}, Skipped: {result.skipped_count}, Total Outputs: {result.total_outputs}")
            print(f"[ProgressManager] Preview: {self.progress_manager.get_preview_text()}")
        except Exception as e:
            print(f"[ProgressManager] Calculation failed: {e}")
            # Fallback: assume all files valid, no variants
            self.progress_manager.total_outputs = len(files)
    
    def set_progress(self, value):
        """Set progress bar value (0-100) - updates green overall progress bar."""
        # Update the green total_progress_bar in output footer (0.0-1.0 scale)
        self.output_footer.set_total_progress(value / 100.0)
    
    @pyqtSlot(int, float)
    def on_file_progress(self, file_index, progress):
        """Handle individual file progress update - updates blue file progress bar."""
        # Update file list item progress
        self.drag_drop_area.set_file_progress(file_index, progress)
        
        # Update blue bar (current file) in output footer
        self.output_footer.set_file_progress(progress)
        
        # NOTE: Green bar (overall progress) is updated via set_progress() signal,
        # not here - to avoid conflicting updates
    
    def on_file_completed(self, source_file, output_file):
        """Handle completed file conversion."""
        import os
        source_name = os.path.basename(source_file)
        output_name = os.path.basename(output_file)
        self.update_status(f"[OK] Converted: {source_name} → {output_name}")
        
        # Ensure blue bar reaches 100% for this file
        self.output_footer.set_file_progress(1.0)
        
        # Increment progress manager (each output variant completes)
        progress_percentage = self.progress_manager.increment_progress(count=1)
        
        # Update green total progress bar with accurate percentage
        self.output_footer.set_total_progress(progress_percentage / 100.0)
        
        # Mark the file as completed in the list
        # Find the file index
        for i, f in enumerate(self.drag_drop_area.file_list):
            if f == source_file:
                self.drag_drop_area.set_file_completed(i)
                self._completed_files_count += 1
                break
    
    def on_conversion_finished(self, success, message):
        """Handle conversion completion (LEGACY - for backward compatibility)."""
        # Reset progress manager state
        self.progress_manager.reset()
        
        # Reset UI state
        self._reset_conversion_ui()
        
        self.update_status(message)
        
        # LEGACY: Old engines may call this - try to extract counts or show basic message
        import re
        match = re.search(r'(\d+)\s+files?\s+processed', message)
        if match:
            successful = int(match.group(1))
            # Use localized toast instead of dialog
            self.drag_drop_area.show_conversion_toast(successful, 0, 0, 0)
        # If no counts found, do nothing (engine should use conversion_completed signal)
    
    def _on_conversion_completed(self, successful, failed, skipped, stopped):
        """Handle conversion completion with detailed counts (NEW unified handler)."""
        # Reset progress manager state
        self.progress_manager.reset()
        
        # Reset UI state
        self._reset_conversion_ui()
        
        # Show unified conversion summary toast (replacing dialog)
        self.drag_drop_area.show_conversion_toast(successful, failed, skipped, stopped)
    
    def _reset_conversion_ui(self):
        """Reset UI elements after conversion."""
        # Reset footer state
        self.output_footer.set_converting(False)
        self.output_footer.reset_progress()
        
        self._completed_files_count = 0
