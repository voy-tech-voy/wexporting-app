"""
Preset Conversion Engine - Async execution with immediate cancellation.

Follows the same pattern as TargetSizeConversionEngine and ManualModeConversionEngine:
- QThread-based for non-blocking execution
- subprocess.Popen with poll loop for cancellation
- Progress signals for UI updates
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path
from PySide6.QtCore import QThread, Signal
import subprocess
import os
import sys
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
    progress_updated = Signal(int)                    # Overall percentage (0-100)
    file_progress_updated = Signal(int, float)        # (file_index, 0.0-1.0)
    status_updated = Signal(str)                      # Status messages
    file_completed = Signal(str, str)                 # (source_path, output_path)
    file_failed = Signal(str)                         # (source_path)
    file_skipped = Signal(str)                        # (source_path)
    file_stopped = Signal(str)                        # (source_path)
    conversion_completed = Signal(int, int, int, int) # (successful, failed, skipped, stopped)
    
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
        
        for i, input_item in enumerate(self.files):
            # input_item can be a str (file path) or a dict (sequence info)
            input_path = input_item if isinstance(input_item, str) else input_item.get('preview_file', '')
            
            if self.should_stop:
                print(f"[PresetEngine] Conversion stopped by user")
                self.file_stopped.emit(input_path)  # Emit stopped signal
                break
            
            # Update file progress (reset to 0 for new file)
            self.file_progress_updated.emit(i, 0.0)
            
            # Update overall progress
            progress_pct = int((i / total_files) * 100)
            self.progress_updated.emit(progress_pct)
            
            # Convert file/item
            try:
                success = self._convert_file(input_item, i, total_files)
                if success is None:
                    pass  # Already counted in _convert_file via skipped_files
                elif success:
                    self.successful_conversions += 1
                else:
                    self.failed_conversions += 1
                    self.file_failed.emit(input_path)  # Emit failed signal
            except Exception as e:
                print(f"[PresetEngine] Error converting {input_path}: {e}")
                self.failed_conversions += 1
                self.status_updated.emit(f"Error: {str(e)}")
                self.file_failed.emit(input_path)  # Emit failed signal
        
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
    
    def _convert_file(self, input_item: Any, file_index: int, total_files: int) -> bool:
        """
        Convert a single file or sequence using the preset.
        
        Args:
            input_item: Path to input file (str) or sequence info (dict)
            file_index: Index of current item (for progress)
            total_files: Total number of items
            
        Returns:
            True if successful, False otherwise
        """
        # Handle sequence vs single file
        is_sequence = isinstance(input_item, dict)
        if is_sequence:
            input_path = input_item.get('preview_file', '')
            input_name = input_item.get('name', 'Sequence')
            sequence_files = input_item.get('files', [])
        else:
            input_path = input_item
            input_name = Path(input_path).name
            sequence_files = []
            
        input_p = Path(input_path)

        # Enforce accepted_extensions constraint
        preset = self.orchestrator.selected_preset
        if preset and preset.constraints.accepted_extensions:
            file_ext = input_p.suffix.lower()
            allowed = [e.lower() for e in preset.constraints.accepted_extensions]
            if file_ext not in allowed:
                self.status_updated.emit(f"[SKIP] {input_name}: not a supported format for this preset (expected {', '.join(allowed)})")
                self.skipped_files += 1
                self.file_skipped.emit(input_path)
                return None  # Treated as "skipped" by caller

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
        self.status_updated.emit(f"Analyzing: {input_name}")
        meta = self.orchestrator.analyze_file(str(input_path))
        
        # Get parameter values
        param_values = self.orchestrator.get_parameter_values()
        
        # Render filename suffix from YAML template
        filename_suffix = ""
        if preset.pipeline and preset.pipeline[0].filename_suffix:
            suffix_context = {
                'meta': meta,
                'input_stem': input_p.stem,  # Available as {{ input_stem }} in suffix templates
                **param_values,
            }
            filename_suffix = self.orchestrator._builder.render_filename_suffix(preset.pipeline[0], suffix_context)
        else:
            filename_suffix = "_preset"

        # Construct output path
        output_ext = preset.output_extension if preset.output_extension else input_p.suffix
        output_path = output_dir / f"{input_p.stem}{filename_suffix}{output_ext}"

        # Ensure the output directory (and any subfolders in filename_suffix) exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build context for command templates
        from client.utils.gpu_detector import get_gpu_detector
        gpu_detector = get_gpu_detector(self.orchestrator._registry.get_tool_path('ffmpeg'))
        h264_encoder, encoder_type = gpu_detector.get_best_encoder("MP4 (H.264)", prefer_gpu=True)

        def get_h264_flags(quality: int) -> str:
            """Helper for Jinja templates to get correct quality flags for the current encoder."""
            params = gpu_detector.get_encoder_params(h264_encoder, quality)
            return " ".join([f"-{k} {v}" for k, v in params.items()])

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
            'get_h264_flags': get_h264_flags,
            'is_sequence': is_sequence,
            'sequence_files': sequence_files,
            'sequence_count': len(sequence_files),
            **param_values,
        }
        
        # Execute pipeline steps
        self.status_updated.emit(f"Converting: {input_name}")
        
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
                # Fallback: check for sequence output (e.g. %03d frames - no single output file)
                seq_parent = output_path.parent
                seq_stem = output_path.stem
                sequence_matches = list(seq_parent.glob(f"{seq_stem}*"))
                if sequence_matches:
                    print(f"[PresetEngine] Sequence output detected: {len(sequence_matches)} file(s) in {seq_parent}")
                    self.file_completed.emit(str(input_path), str(seq_parent))
                    self.file_progress_updated.emit(file_index, 1.0)
                    return True
                print(f"[PresetEngine] ERROR: Pipeline succeeded but output file not created!")
                print(f"[PresetEngine] Expected output: {output_path}")
                return False
        
        return False
    
    def _execute_command(self, cmd: str, step_num: int, total_steps: int) -> bool:
        """
        Execute a command with cancellation support and real-time progress tracking.

        Follows conversion_run_skill.md:
        - startupinfo + CREATE_NO_WINDOW for silent Windows execution
        - Daemon stderr drain thread to prevent buffer deadlock
        - Main-thread readline loop with inline should_stop check for immediate cancellation
        """
        import threading
        import re

        def read_stderr(proc, out_list):
            """Drain stderr line-by-line in background to prevent deadlock."""
            try:
                for line in proc.stderr:
                    out_list.append(line)
            except:
                pass

        try:
            # Detect if this is an FFmpeg command for progress parsing
            is_ffmpeg = 'ffmpeg' in cmd.lower()

            if is_ffmpeg:
                # Inject -progress pipe:1 -nostats right after the ffmpeg executable
                ffmpeg_pattern = r'["\']?[^"\']*[/\\]ffmpeg[^"\']*\.exe["\']?'
                match = re.search(ffmpeg_pattern, cmd, re.IGNORECASE)
                if match:
                    insert_pos = match.end()
                    cmd_with_progress = cmd[:insert_pos] + ' -progress pipe:1 -nostats' + cmd[insert_pos:]
                else:
                    cmd_with_progress = cmd
            else:
                cmd_with_progress = cmd

            from client.utils.conversion_logger import log_conversion_start, log_conversion_success, log_conversion_error
            log_session = log_conversion_start("preset", cmd_with_progress, f"step_{step_num}_of_{total_steps}")

            # Silent Windows execution: both startupinfo and CREATE_NO_WINDOW required
            startupinfo = None
            creationflags = 0
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            _cwd = sys._MEIPASS if getattr(sys, 'frozen', False) else None
            self._current_process = subprocess.Popen(
                cmd_with_progress,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                cwd=_cwd,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )

            process = self._current_process

            # Daemon stderr drain thread — prevents deadlock on Windows
            stderr_output = []
            stderr_thread = threading.Thread(target=read_stderr, args=(process, stderr_output), daemon=True)
            stderr_thread.start()

            if is_ffmpeg:
                # Main-thread readline loop: check should_stop on every progress tick
                time_pattern = re.compile(r'out_time_ms=(\d+)')
                while True:
                    if self.should_stop:
                        print(f"[PresetEngine] Cancelling command...")
                        process.kill()
                        self._current_process = None
                        return False

                    line = process.stdout.readline()
                    if not line:
                        break

                    time_match = time_pattern.search(line)
                    if time_match:
                        current_time_s = int(time_match.group(1)) / 1000000.0
                        # Progress available here if needed: current_time_s / meta.duration

                    if 'progress=end' in line:
                        break
            else:
                # Non-FFmpeg: drain stdout in background, check should_stop via poll
                def drain_stdout(proc):
                    try:
                        for _ in proc.stdout:
                            pass
                    except:
                        pass

                stdout_thread = threading.Thread(target=drain_stdout, args=(process,), daemon=True)
                stdout_thread.start()

                while process.poll() is None:
                    if self.should_stop:
                        print(f"[PresetEngine] Cancelling command...")
                        process.kill()
                        self._current_process = None
                        return False
                    time.sleep(0.1)

            if process:
                process.wait()
            stderr_thread.join(timeout=1.0)

            returncode = process.returncode

            if returncode != 0:
                stderr_text = "".join(stderr_output)
                log_conversion_error(log_session, stderr_text, returncode)
                print(f"[PresetEngine] Command failed with code {returncode}")
                print(f"[PresetEngine] === STDERR (last 500 chars) ===")
                print(stderr_text[-500:] if len(stderr_text) > 500 else stderr_text)
                print(f"[PresetEngine] === END STDERR ===")
            else:
                log_conversion_success(log_session)

            self._current_process = None
            return returncode == 0

        except Exception as e:
            if 'log_session' in locals():
                import traceback
                log_conversion_error(log_session, f"Exception: {str(e)}\n{traceback.format_exc()}", -1)
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
