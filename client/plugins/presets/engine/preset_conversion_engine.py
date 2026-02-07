"""
Preset Conversion Engine - Async execution with immediate cancellation.

Follows the same pattern as TargetSizeConversionEngine and ManualModeConversionEngine:
- QThread-based for non-blocking execution
- subprocess.Popen with poll loop for cancellation
- Progress signals for UI updates
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
import subprocess
import os
import time

if TYPE_CHECKING:
    from client.plugins.presets.orchestrator import PresetOrchestrator


class PresetConversionEngine(QThread):
    """
    Async preset conversion engine.
    
    Runs preset conversions in a background thread, enabling:
    - Non-blocking UI during long operations
    - Immediate cancellation via process.kill()
    - Real-time progress updates
    
    Signals:
        progress_updated: Overall progress percentage (0-100)
        file_progress_updated: Per-file progress (file_index, 0.0-1.0)
        status_updated: Status messages
        file_completed: File completion (source_path, output_path)
        conversion_completed: Final results (successful, failed, skipped, stopped)
    """
    
    # Signals matching other conversion engines
    progress_updated = pyqtSignal(int)                    # Overall percentage (0-100)
    file_progress_updated = pyqtSignal(int, float)        # (file_index, 0.0-1.0)
    status_updated = pyqtSignal(str)                      # Status messages
    file_completed = pyqtSignal(str, str)                 # (source_path, output_path)
    conversion_completed = pyqtSignal(int, int, int, int) # (successful, failed, skipped, stopped)
    
    def __init__(self, files: List[str], params: Dict[str, Any], orchestrator: 'PresetOrchestrator'):
        """
        Initialize the preset conversion engine.
        
        Args:
            files: List of file paths to convert
            params: Conversion parameters (output_mode, organized_name, custom_path)
            orchestrator: PresetOrchestrator instance for command building and analysis
        """
        super().__init__()
        self.files = files
        self.params = params
        self.orchestrator = orchestrator
        
        # Cancellation support
        self.should_stop = False
        self._current_process: Optional[subprocess.Popen] = None
        
        # Counters
        self.successful_conversions = 0
        self.failed_conversions = 0
        self.skipped_files = 0
    
    def stop_conversion(self):
        """
        Stop the conversion immediately.
        
        This method can be called from the main thread to cancel an ongoing conversion.
        It sets the stop flag and kills any running subprocess.
        """
        self.should_stop = True
        if self._current_process:
            try:
                self._current_process.kill()
                self._current_process.wait(timeout=2)  # Wait for cleanup
                self._current_process = None
            except Exception as e:
                print(f"[PresetEngine] Error killing process: {e}")
    
    def run(self):
        """
        Main conversion loop - runs in background thread.
        
        Iterates through files, builds commands via orchestrator, and executes
        them with cancellation support.
        """
        total_files = len(self.files)
        
        print(f"[PresetEngine] Starting conversion of {total_files} files")
        
        for i, input_path in enumerate(self.files):
            if self.should_stop:
                print(f"[PresetEngine] Conversion stopped by user")
                break
            
            # Update file progress (reset to 0 for new file)
            self.file_progress_updated.emit(i, 0.0)
            
            # Update overall progress
            progress_pct = int((i / total_files) * 100)
            self.progress_updated.emit(progress_pct)
            
            # Convert file
            try:
                success = self._convert_file(input_path, i, total_files)
                if success:
                    self.successful_conversions += 1
                else:
                    self.failed_conversions += 1
            except Exception as e:
                print(f"[PresetEngine] Error converting {input_path}: {e}")
                self.failed_conversions += 1
                self.status_updated.emit(f"Error: {str(e)}")
        
        # Calculate stopped count
        stopped_count = total_files - (self.successful_conversions + self.failed_conversions + self.skipped_files)
        
        # Emit completion
        self.conversion_completed.emit(
            self.successful_conversions,
            self.failed_conversions,
            self.skipped_files,
            stopped_count if self.should_stop else 0
        )
        
        print(f"[PresetEngine] Conversion complete: {self.successful_conversions} success, {self.failed_conversions} failed, {stopped_count} stopped")
    
    def _convert_file(self, input_path: str, file_index: int, total_files: int) -> bool:
        """
        Convert a single file using the preset.
        
        Args:
            input_path: Path to input file
            file_index: Index of current file (for progress)
            total_files: Total number of files
            
        Returns:
            True if successful, False otherwise
        """
        input_p = Path(input_path)
        
        # Determine output directory from params
        output_mode = self.params.get('output_mode', 'source')
        organized_name = self.params.get('organized_name', 'output')
        custom_path = self.params.get('custom_path')
        
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
        
        # Get preset from orchestrator
        preset = self.orchestrator.selected_preset
        if not preset:
            self.status_updated.emit("No preset selected")
            return False
        
        # Analyze media for smart presets
        self.status_updated.emit(f"Analyzing: {input_p.name}")
        meta = self.orchestrator.analyze_file(str(input_path))
        
        # Get parameter values
        param_values = self.orchestrator.get_parameter_values()
        
        # Render filename suffix from YAML template
        filename_suffix = ""
        if preset.pipeline and preset.pipeline[0].filename_suffix:
            suffix_context = {
                'meta': meta,
                **param_values,
            }
            filename_suffix = self.orchestrator._builder.render_filename_suffix(preset.pipeline[0], suffix_context)
        else:
            filename_suffix = "_preset"
        
        # Construct output path
        output_path = output_dir / f"{input_p.stem}{filename_suffix}{input_p.suffix}"
        
        # Build context for command templates
        from client.utils.gpu_detector import get_gpu_detector
        gpu_detector = get_gpu_detector(self.orchestrator._registry.get_tool_path('ffmpeg'))
        h264_encoder, encoder_type = gpu_detector.get_best_encoder("MP4 (H.264)", prefer_gpu=True)
        
        # Normalize paths for FFmpeg
        input_path_normalized = str(input_path).replace('\\', '/')
        output_path_normalized = str(output_path).replace('\\', '/')
        output_path_no_ext_normalized = str(output_dir / f"{input_p.stem}{filename_suffix}").replace('\\', '/')
        trf_filename = f"{input_p.stem}{filename_suffix}"
        
        context = {
            'input_path': input_path_normalized,
            'output_path': output_path_normalized,
            'output_path_no_ext': output_path_no_ext_normalized,
            'output_path_no_ext_escaped': trf_filename,
            'meta': meta,
            'gpu_encoder': h264_encoder,
            'gpu_type': encoder_type.value,
            **param_values,
        }
        
        # Execute pipeline steps
        self.status_updated.emit(f"Converting: {input_p.name}")
        
        if not preset.pipeline:
            self.status_updated.emit(f"No pipeline steps for preset: {preset.name}")
            return False
        
        pipeline_success = True
        total_steps = len(preset.pipeline)
        
        for step_idx, step in enumerate(preset.pipeline):
            if self.should_stop:
                return False
            
            # Build command
            cmd = self.orchestrator._builder.build_command(step, context)
            step_num = step_idx + 1
            
            print(f"[PresetEngine] ===== STEP {step_num}/{total_steps}: {step.description} =====")
            print(f"[PresetEngine] {cmd}")
            
            # Update status
            self.status_updated.emit(f"Step {step_num}/{total_steps}: {step.description}")
            
            # Execute command with cancellation support
            success = self._execute_command(cmd, step_num, total_steps)
            
            if not success:
                pipeline_success = False
                print(f"[PresetEngine] [X] Step {step_num} failed: {step.description}")
                break
            else:
                print(f"[PresetEngine] [OK] Step {step_num} completed: {step.description}")
        
        # Check if output file was created
        if pipeline_success:
            if output_path.exists():
                self.file_completed.emit(str(input_path), str(output_path))
                self.file_progress_updated.emit(file_index, 1.0)
                return True
            else:
                print(f"[PresetEngine] ERROR: Pipeline succeeded but output file not created!")
                print(f"[PresetEngine] Expected output: {output_path}")
                return False
        
        return False
    
    def _execute_command(self, cmd: str, step_num: int, total_steps: int) -> bool:
        """
        Execute a command with cancellation support and real-time progress tracking.
        
        Uses the unified async pattern from target_size and manual engines:
        - subprocess.Popen with -progress pipe:1 for FFmpeg
        - Async threads for stdout (progress) and stderr (error capture)
        - Poll loop for immediate cancellation
        
        Args:
            cmd: Command to execute
            step_num: Current step number (for progress)
            total_steps: Total number of steps
            
        Returns:
            True if command succeeded, False otherwise
        """
        import threading
        import re
        
        def drain_pipe(pipe, collected: list):
            """Drain pipe in background thread to prevent buffer deadlock."""
            try:
                while True:
                    chunk = pipe.read(4096)
                    if not chunk:
                        break
                    collected.append(chunk)
            except:
                pass
        
        try:
            # Detect if this is an FFmpeg command for progress parsing
            is_ffmpeg = 'ffmpeg' in cmd.lower()
            
            if is_ffmpeg:
                # Inject progress flags into command string (preserves complex arguments)
                # Find the position after the ffmpeg executable
                import re
                # Match ffmpeg executable (handles paths with spaces)
                ffmpeg_pattern = r'(["\']?[^"\']*ffmpeg[^"\']*\.exe["\']?|ffmpeg)'
                match = re.search(ffmpeg_pattern, cmd, re.IGNORECASE)
                
                if match:
                    insert_pos = match.end()
                    # Insert progress flags right after ffmpeg executable
                    cmd_with_progress = cmd[:insert_pos] + ' -progress pipe:1 -nostats' + cmd[insert_pos:]
                else:
                    # Fallback: just use original command
                    cmd_with_progress = cmd
            else:
                # Non-FFmpeg command, run as-is
                cmd_with_progress = cmd
            
            # Create process with Popen (always use shell=True to preserve complex arguments)
            self._current_process = subprocess.Popen(
                cmd_with_progress,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Store reference for poll loop
            process = self._current_process
            
            # Start stderr drain thread (prevents deadlock)
            stderr_chunks = []
            stderr_thread = threading.Thread(target=drain_pipe, args=(process.stderr, stderr_chunks))
            stderr_thread.daemon = True
            stderr_thread.start()
            
            # Parse progress from stdout if FFmpeg
            if is_ffmpeg:
                time_pattern = re.compile(r'out_time_ms=(\d+)')
                
                def parse_progress():
                    """Parse FFmpeg progress output in background thread."""
                    try:
                        while True:
                            line = process.stdout.readline()
                            if not line:
                                break
                            
                            line_str = line if isinstance(line, str) else line.decode('utf-8', errors='ignore')
                            
                            # Parse time progress
                            time_match = time_pattern.search(line_str)
                            if time_match:
                                current_time_ms = int(time_match.group(1))
                                current_time_s = current_time_ms / 1000000.0  # microseconds to seconds
                                
                                # Emit progress (we don't have duration here, so just emit raw time)
                                # The engine will handle overall progress calculation
                                # For now, just indicate activity
                                pass
                            
                            # Check for completion
                            if 'progress=end' in line_str:
                                break
                    except:
                        pass
                
                stdout_thread = threading.Thread(target=parse_progress)
                stdout_thread.daemon = True
                stdout_thread.start()
            else:
                # Drain stdout for non-FFmpeg commands
                stdout_chunks = []
                stdout_thread = threading.Thread(target=drain_pipe, args=(process.stdout, stdout_chunks))
                stdout_thread.daemon = True
                stdout_thread.start()
            
            # Poll loop for cancellation check
            while process.poll() is None:
                if self.should_stop:
                    print(f"[PresetEngine] Cancelling command...")
                    process.kill()
                    process.wait(timeout=1)  # Wait for process to terminate
                    self._current_process = None
                    return False
                
                # Sleep briefly to avoid busy-waiting
                time.sleep(0.1)  # Check every 100ms
            
            # Wait for threads to finish
            stderr_thread.join(timeout=1)
            if is_ffmpeg:
                stdout_thread.join(timeout=1)
            
            # Get return code
            returncode = process.returncode
            
            # Capture stderr for error reporting
            if returncode != 0:
                stderr_output = b''.join(stderr_chunks).decode('utf-8', errors='ignore')
                print(f"[PresetEngine] Command failed with code {returncode}")
                print(f"[PresetEngine] === STDERR (last 500 chars) ===")
                print(stderr_output[-500:] if len(stderr_output) > 500 else stderr_output)
                print(f"[PresetEngine] === END STDERR ===")
            
            self._current_process = None
            return returncode == 0
            
        except Exception as e:
            print(f"[PresetEngine] Exception executing command: {e}")
            import traceback
            traceback.print_exc()
            if self._current_process:
                try:
                    self._current_process.kill()
                except:
                    pass
                self._current_process = None
            return False
