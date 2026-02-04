#!/usr/bin/env python3
"""
Windows Error Reporter
Handles error reporting and logging for Windows ImgApp
"""

import sys
import os
import json
import logging
import platform
from pathlib import Path
from datetime import datetime
import traceback

class WindowsErrorReporter:
    """Windows-specific error reporting and logging"""
    
    def __init__(self):
        """Initialize Windows error reporter"""
        self.setup_logging()
        self.app_info = self.gather_app_info()
    
    def setup_logging(self):
        """Set up comprehensive logging for Windows"""
        try:
            self.log_dir = self.get_log_directory()
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # Create log file with timestamp
            log_filename = f"imgapp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            self.log_file = self.log_dir / log_filename
            
            # Set up logging configuration
            logging.basicConfig(
                level=logging.WARNING,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(str(self.log_file), encoding='utf-8')
                ]
            )
            
            self.logger = logging.getLogger('ImgApp')
            self.logger.info(f"Logging initialized: {self.log_file}")
            
        except Exception as e:
            print(f"Warning: Could not setup logging: {e}")
            self.logger = None
    
    def get_log_directory(self):
        """Get the appropriate log directory for Windows"""
        possible_dirs = []
        
        # PRIORITY 1: Same directory as .exe (for production builds)
        try:
            if getattr(sys, 'frozen', False):
                exe_path = Path(sys.executable)
                log_dir = exe_path.parent / "ImgApp_Logs"
                possible_dirs.append(log_dir)
        except Exception:
            pass
        
        # PRIORITY 2: Same directory as main.py (for development)
        try:
            main_script = Path(__file__).parent
            log_dir = main_script / "ImgApp_Logs"
            possible_dirs.append(log_dir)
        except Exception:
            pass
        
        # PRIORITY 3: User Documents folder
        try:
            docs_path = Path.home() / "Documents" / "ImgApp_Logs"
            possible_dirs.append(docs_path)
        except Exception:
            pass
        
        # PRIORITY 4: AppData Local
        try:
            appdata = Path(os.environ.get('LOCALAPPDATA', '')) / "ImgApp" / "Logs"
            possible_dirs.append(appdata)
        except Exception:
            pass
        
        # Try each directory until one works
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
        
        # Last resort - current directory
        return Path.cwd() / "ImgApp_Logs"
    
    def gather_app_info(self):
        """Gather comprehensive application information"""
        info = {
            "timestamp": datetime.now().isoformat(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "architecture": platform.architecture(),
                "platform_string": platform.platform()
            },
            "python": {
                "version": sys.version,
                "executable": sys.executable,
                "path": sys.path[:5],  # First 5 path entries
                "frozen": getattr(sys, 'frozen', False)
            },
            "environment": {
                "working_directory": str(Path.cwd()),
                "user": os.environ.get('USERNAME', 'Unknown'),
                "computername": os.environ.get('COMPUTERNAME', 'Unknown'),
                "temp": os.environ.get('TEMP', 'Unknown')
            }
        }
        
        # Check available modules
        modules_to_check = ['PyQt5', 'requests', 'PIL', 'pathlib', 'json']
        info["modules"] = {}
        
        for module in modules_to_check:
            try:
                __import__(module)
                info["modules"][module] = "available"
            except ImportError:
                info["modules"][module] = "missing"
        
        return info
    
    def log_error(self, error, context="", additional_info=None):
        """Log an error with full context"""
        try:
            error_data = {
                "timestamp": datetime.now().isoformat(),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
                "traceback": traceback.format_exc(),
                "app_info": self.app_info
            }
            
            if additional_info:
                error_data["additional_info"] = additional_info
            
            # Log to file
            if self.logger:
                self.logger.error(f"ERROR in {context}: {error}")
                self.logger.debug(f"Full traceback: {traceback.format_exc()}")
            
            # Save detailed error report
            error_filename = f"error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            error_file = self.log_dir / error_filename
            
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(error_data, f, indent=2, ensure_ascii=False)
            
            if self.logger:
                self.logger.info(f"Detailed error report saved: {error_file}")
            
            return error_file
            
        except Exception as e:
            print(f"Failed to log error: {e}")
            return None
    
    def log_info(self, message, context=""):
        """Log informational message"""
        try:
            if self.logger:
                self.logger.info(f"{context}: {message}" if context else message)
        except Exception as e:
            print(f"Failed to log info: {e}")
    
    def log_warning(self, message, context=""):
        """Log warning message"""
        try:
            if self.logger:
                self.logger.warning(f"{context}: {message}" if context else message)
        except Exception as e:
            print(f"Failed to log warning: {e}")
    
    def create_diagnostic_report(self):
        """Create comprehensive diagnostic report"""
        try:
            diagnostic_data = {
                "report_type": "diagnostic",
                "generated": datetime.now().isoformat(),
                "app_info": self.app_info,
                "log_directory": str(self.log_dir),
                "log_file": str(self.log_file) if hasattr(self, 'log_file') else None
            }
            
            # Test system capabilities
            diagnostic_data["system_tests"] = self.run_system_tests()
            
            # Save diagnostic report
            diag_filename = f"diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            diag_file = self.log_dir / diag_filename
            
            with open(diag_file, 'w', encoding='utf-8') as f:
                json.dump(diagnostic_data, f, indent=2, ensure_ascii=False)
            
            if self.logger:
                self.logger.info(f"Diagnostic report created: {diag_file}")
            
            return diag_file
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create diagnostic report: {e}")
            return None
    
    def run_system_tests(self):
        """Run basic system capability tests"""
        tests = {}
        
        # Test file system access
        try:
            test_file = self.log_dir / "test_write.tmp"
            test_file.write_text("test content")
            content = test_file.read_text()
            test_file.unlink()
            tests["filesystem_write"] = "[OK] OK" if content == "test content" else "[X] Failed"
        except Exception as e:
            tests["filesystem_write"] = f"[X] Failed: {e}"
        
        # Test PyQt5 availability
        try:
            from PyQt6.QtWidgets import QApplication
            tests["pyqt5_import"] = "[OK] OK"
            
            # Test QApplication creation
            try:
                app = QApplication.instance()
                if app is None:
                    app = QApplication([])
                tests["qapplication_create"] = "[OK] OK"
            except Exception as e:
                tests["qapplication_create"] = f"[X] Failed: {e}"
                
        except ImportError as e:
            tests["pyqt5_import"] = f"[X] Failed: {e}"
        
        # Test network connectivity (basic)
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            tests["network_connectivity"] = "[OK] OK"
        except Exception as e:
            tests["network_connectivity"] = f"[X] Failed: {e}"
        
        return tests
    
    def get_recent_logs(self, count=10):
        """Get list of recent log files"""
        try:
            log_files = []
            for file in self.log_dir.glob("*.log"):
                log_files.append({
                    "name": file.name,
                    "path": str(file),
                    "size": file.stat().st_size,
                    "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                })
            
            # Sort by modification time, most recent first
            log_files.sort(key=lambda x: x["modified"], reverse=True)
            return log_files[:count]
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get recent logs: {e}")
            return []

# Global error reporter instance
_error_reporter = None

def get_error_reporter():
    """Get the global error reporter instance"""
    global _error_reporter
    if _error_reporter is None:
        _error_reporter = WindowsErrorReporter()
    return _error_reporter

def log_error(error, context="", additional_info=None):
    """Convenient function to log errors"""
    return get_error_reporter().log_error(error, context, additional_info)

def log_info(message, context=""):
    """Convenient function to log info"""
    get_error_reporter().log_info(message, context)

def log_warning(message, context=""):
    """Convenient function to log warnings"""
    get_error_reporter().log_warning(message, context)
