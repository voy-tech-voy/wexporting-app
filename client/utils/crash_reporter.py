#!/usr/bin/env python3
"""
Emergency Windows Crash Reporter
Handles ALL possible app startup failures, even before GUI can load
"""

import sys
import os
import traceback
import logging
import json
import platform
from pathlib import Path
from datetime import datetime
import subprocess

class EmergencyCrashReporter:
    """Emergency reporter that works even when everything else fails"""
    
    def __init__(self, force_init=True):
        """Initialize with minimal dependencies"""
        self.startup_time = datetime.now()
        self.errors = []
        self.warnings = []
        self.init_steps = []
        self.crash_info = {}
        
        try:
            self.log_dir = self._get_emergency_log_dir()
            if force_init:
                self._setup_emergency_logging()
            self._log_init_step("Emergency reporter initialized")
        except Exception as e:
            # Last resort - write to current directory
            self.log_dir = Path.cwd() / "emergency_logs"
            self.log_dir.mkdir(exist_ok=True)
            print(f"EMERGENCY: Failed to setup logging: {e}")
    
    def _get_emergency_log_dir(self):
        """Get emergency log directory that will work in any scenario"""
        possible_dirs = []
        
        # PRIORITY 1: Same directory as the .exe (for production)
        try:
            if getattr(sys, 'frozen', False):
                # Running from PyInstaller bundle
                exe_path = Path(sys.executable)
                log_dir = exe_path.parent / "ImgApp_Logs"
                possible_dirs.append(log_dir)
        except Exception:
            pass
        
        # PRIORITY 2: Next to main.py (for development)
        try:
            main_script = Path(__file__).parent
            log_dir = main_script / "ImgApp_Logs"
            possible_dirs.append(log_dir)
        except Exception:
            pass
        
        # PRIORITY 3: User Documents
        try:
            import os
            docs_path = Path.home() / "Documents" / "ImgApp_Logs"
            possible_dirs.append(docs_path)
        except Exception:
            pass
        
        # PRIORITY 4: Temp directory
        try:
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / "ImgApp_Logs"
            possible_dirs.append(temp_dir)
        except Exception:
            pass
        
        # Try each directory
        for log_dir in possible_dirs:
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                # Test write access
                test_file = log_dir / "test_write.tmp"
                test_file.write_text("test")
                test_file.unlink()
                return log_dir
            except Exception:
                continue
        
        # Last resort
        return Path.cwd() / "emergency_logs"
    
    def _setup_emergency_logging(self):
        """Set up emergency logging with minimal dependencies"""
        try:
            self.log_file = self.log_dir / f"emergency_startup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            
            # Basic logging setup
            logging.basicConfig(
                level=logging.WARNING,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(str(self.log_file), encoding='utf-8')
                ]
            )
            
            self.logger = logging.getLogger('emergency')
            self.logger.info(f"Emergency logging initialized: {self.log_file}")
            
        except Exception as e:
            print(f"Failed to setup emergency logging: {e}")
            self.logger = None
    
    def _log_init_step(self, step):
        """Log an initialization step"""
        try:
            timestamp = datetime.now()
            duration = (timestamp - self.startup_time).total_seconds() * 1000
            
            step_info = {
                "step": step,
                "timestamp": timestamp.isoformat(),
                "duration_ms": round(duration, 1),
                "success": True
            }
            
            self.init_steps.append(step_info)
            
            if self.logger:
                self.logger.info(f"[OK] INIT: {step} ({duration:.1f}ms)")
            else:
                print(f"[OK] INIT: {step}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to log init step: {e}")
    
    def _log_error(self, error, context="unknown"):
        """Log an error during initialization"""
        try:
            error_info = {
                "error": str(error),
                "context": context,
                "timestamp": datetime.now().isoformat(),
                "traceback": traceback.format_exc()
            }
            
            self.errors.append(error_info)
            
            if self.logger:
                self.logger.error(f"[X] ERROR: {context}: {error}")
                self.logger.debug(f"Traceback: {traceback.format_exc()}")
            else:
                print(f"[X] ERROR: {context}: {error}")
                
        except Exception as e:
            print(f"Failed to log error: {e}")
    
    def check_python_environment(self):
        """Check Python environment health"""
        try:
            self._log_init_step("Checking Python environment")
            
            checks = {
                "python_version": sys.version,
                "platform": platform.platform(),
                "executable": sys.executable,
                "path": sys.path[:5],  # First 5 entries
                "modules": {}
            }
            
            # Check critical modules
            critical_modules = ['PySide6', 'requests', 'PIL', 'pathlib']
            for module in critical_modules:
                try:
                    __import__(module)
                    checks["modules"][module] = "[OK] Available"
                except ImportError as e:
                    checks["modules"][module] = f"[X] Missing: {e}"
                    self._log_error(e, f"import_{module}")
            
            self.crash_info["environment"] = checks
            return True
            
        except Exception as e:
            self._log_error(e, "environment_check")
            return False
    
    def check_file_system(self):
        """Check file system access"""
        try:
            self._log_init_step("Checking file system access")
            
            checks = {
                "working_directory": str(Path.cwd()),
                "executable_location": str(Path(sys.argv[0]).parent),
                "write_access": {},
                "critical_files": {}
            }
            
            # Test write access
            test_locations = [
                Path.cwd(),
                Path.home(),
                self.log_dir
            ]
            
            for location in test_locations:
                try:
                    test_file = location / "imgapp_write_test.tmp"
                    test_file.write_text("test")
                    test_file.unlink()
                    checks["write_access"][str(location)] = "[OK] Writable"
                except Exception as e:
                    checks["write_access"][str(location)] = f"[X] Not writable: {e}"
            
            # Check for critical files
            critical_files = ["gui/main_window.py", "core/conversion_engine.py", "config.py"]
            base_path = Path(sys.argv[0]).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
            
            for file in critical_files:
                file_path = base_path / file
                checks["critical_files"][file] = "[OK] Found" if file_path.exists() else "[X] Missing"
            
            self.crash_info["filesystem"] = checks
            return True
            
        except Exception as e:
            self._log_error(e, "filesystem_check")
            return False
    
    def check_gui_dependencies(self):
        """Check GUI framework dependencies"""
        try:
            self._log_init_step("Checking GUI dependencies")
            
            checks = {
                "qt_available": False,
                "display_available": False,
                "widgets": {}
            }
            
            # Check qt import - only test module availability, do NOT create QApplication
            # (main() creates the singleton; PySide6 is strict about only one instance)
            try:
                from PySide6.QtWidgets import QApplication
                checks["qt_available"] = True
                # Just confirm an instance exists or can be accessed
                existing = QApplication.instance()
                checks["qapplication"] = "[OK] Already created" if existing else "[OK] Import OK, not yet created"
                
            except ImportError as e:
                checks["qt_available"] = False
                checks["import_error"] = str(e)
                self._log_error(e, "qt_import")
            
            # Check display availability (Windows)
            try:
                import tkinter
                root = tkinter.Tk()
                root.withdraw()
                root.destroy()
                checks["display_available"] = True
            except Exception as e:
                checks["display_available"] = False
                checks["display_error"] = str(e)
            
            self.crash_info["gui"] = checks
            return checks["qt_available"]
            
        except Exception as e:
            self._log_error(e, "gui_check")
            return False
    
    def report_crash(self, error, crash_point="unknown"):
        """Generate comprehensive crash report"""
        try:
            self._log_init_step(f"Generating crash report for: {crash_point}")
            
            # Calculate runtime
            runtime = (datetime.now() - self.startup_time).total_seconds() * 1000
            
            crash_report = {
                "crash_info": {
                    "timestamp": datetime.now().isoformat(),
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "crash_point": crash_point,
                    "startup_duration_ms": round(runtime, 1),
                    "traceback": traceback.format_exc()
                },
                "system_info": {
                    "platform": platform.platform(),
                    "python_version": sys.version,
                    "executable": sys.executable,
                    "working_directory": str(Path.cwd()),
                    "frozen": getattr(sys, 'frozen', False)
                },
                "initialization_steps": self.init_steps,
                "errors": self.errors,
                "warnings": self.warnings,
                "diagnostics": self.crash_info
            }
            
            # Save JSON report
            json_file = self.log_dir / f"EMERGENCY_CRASH_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(crash_report, f, indent=2)
            
            # Create human-readable report
            txt_file = self.log_dir / f"EMERGENCY_CRASH_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            self._create_readable_report(crash_report, txt_file)
            
            if self.logger:
                self.logger.critical(f"Crash report generated: {json_file}")
                self.logger.critical(f"Human-readable report: {txt_file}")
            
            return json_file, txt_file
            
        except Exception as e:
            # Emergency fallback
            emergency_file = Path.cwd() / f"EMERGENCY_FALLBACK_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            try:
                with open(emergency_file, 'w', encoding='utf-8') as f:
                    f.write(f"EMERGENCY CRASH REPORT\\n")
                    f.write(f"Time: {datetime.now()}\\n")
                    f.write(f"Original Error: {error}\\n")
                    f.write(f"Report Generation Error: {e}\\n")
                    f.write(f"Traceback: {traceback.format_exc()}\\n")
                print(f"Emergency fallback report: {emergency_file}")
            except:
                print(f"CRITICAL: Could not write any crash report!")
    
    def _create_readable_report(self, crash_data, output_file):
        """Create human-readable crash report"""
        try:
            crash_info = crash_data.get("crash_info", {})
            system_info = crash_data.get("system_info", {})
            
            content = f'''
🚨 IMGAPP EMERGENCY CRASH REPORT 🚨
Generated: {crash_info.get("timestamp", "Unknown")}
Startup Duration: {crash_info.get("startup_duration_ms", 0)}ms

CRASH DETAILS
=============
Type: {crash_info.get("error_type", "Unknown")}
Message: {crash_info.get("error_message", "Unknown")}
Point: {crash_info.get("crash_point", "Unknown")}

INITIALIZATION STEPS
====================
'''
            
            for step in crash_data.get("initialization_steps", []):
                status = "[OK]" if step.get("success", False) else "[X]"
                content += f" {len(crash_data.get('initialization_steps', []))}. {status} {step.get('step', 'Unknown step')}\\n"
            
            content += f'''
SYSTEM INFORMATION
==================
Platform: {system_info.get("platform", "Unknown")}
Python: {system_info.get("python_version", "Unknown")}
Executable: {system_info.get("executable", "Unknown")}
Frozen: {system_info.get("frozen", False)}

CRITICAL ANALYSIS
=================
'''
            
            # Analyze common issues
            diagnostics = crash_data.get("diagnostics", {})
            
            # GUI issues
            gui_info = diagnostics.get("gui", {})
            if not gui_info.get("qt_available", True):
                content += "[X] qt not available - GUI framework missing\\n"
            
            # Environment issues  
            env_info = diagnostics.get("environment", {})
            modules = env_info.get("modules", {})
            for module, status in modules.items():
                if "[X]" in status:
                    content += f"[X] {module} module issue: {status}\\n"
            
            content += f'''
TROUBLESHOOTING STEPS
====================
1. Check Python/qt installation
2. Verify file permissions
3. Test with administrator privileges
4. Check antivirus software interference
5. Review full report: {output_file}

EMERGENCY LOG LOCATION
======================
{self.log_dir}
'''
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
        except Exception as e:
            print(f"Failed to create readable report: {e}")

def run_with_crash_protection(main_func, *args, **kwargs):
    """Run main function with comprehensive crash protection"""
    reporter = None
    
    try:
        # Initialize emergency reporter
        reporter = EmergencyCrashReporter()
        
        # Run diagnostics
        reporter.check_python_environment()
        reporter.check_file_system() 
        reporter.check_gui_dependencies()
        
        reporter._log_init_step("Starting main application")
        
        # Run the main function
        result = main_func(*args, **kwargs)
        
        reporter._log_init_step("Application completed successfully")
        return result
        
    except Exception as e:
        if reporter:
            reporter.report_crash(e, "main_application")
        else:
            # Last resort logging
            print(f"CRITICAL ERROR (no reporter): {e}")
            traceback.print_exc()
        
        raise  # Re-raise to maintain normal error handling
    
    except KeyboardInterrupt:
        if reporter:
            reporter._log_init_step("Application interrupted by user")
        raise
    
    except SystemExit:
        if reporter:
            reporter._log_init_step("Application exited normally")
        raise

