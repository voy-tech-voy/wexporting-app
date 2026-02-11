"""
Version Gateway Conductor

Wraps the update_checker module to provide version checking functionality
following the conductor pattern. Handles app version updates (not content updates).
"""

import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from client.utils.update_checker import check_for_updates, UpdateState, UpdateCheckResult

logger = logging.getLogger(__name__)


class VersionCheckWorker(QThread):
    """
    Worker thread to execute version check without blocking UI.
    """
    check_complete = pyqtSignal(object)  # Emits UpdateCheckResult
    
    def __init__(self, timeout=5):
        super().__init__()
        self.timeout = timeout
        
    def run(self):
        """Execute version check."""
        try:
            result = check_for_updates(timeout=self.timeout)
            self.check_complete.emit(result)
        except Exception as e:
            logger.error(f"Version check worker failed: {e}")
            # Emit UP_TO_DATE result to fail gracefully
            self.check_complete.emit(UpdateCheckResult(state=UpdateState.UP_TO_DATE))


class VersionGatewayConductor(QObject):
    """
    Conductor for app version checking (Version Gateway Pattern).
    
    Responsibilities:
    - Check app version against server gateway
    - Determine if update is mandatory, optional, or not needed
    - Emit signals for UI to handle (blocking screen, dialog, etc.)
    
    This is separate from UpdateConductor which handles content updates.
    """
    
    # Signals
    mandatory_update_required = pyqtSignal(object)  # UpdateCheckResult
    optional_update_available = pyqtSignal(object)  # UpdateCheckResult
    up_to_date = pyqtSignal()
    check_failed = pyqtSignal(str)  # Error message
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.last_result = None
        
    def check_version(self, timeout=5):
        """
        Start version check in background.
        Does nothing if check is already running.
        
        Args:
            timeout: HTTP request timeout in seconds
        """
        if self.worker and self.worker.isRunning():
            logger.info("Version check already in progress")
            return
            
        logger.info("Starting version check...")
        self.worker = VersionCheckWorker(timeout=timeout)
        self.worker.check_complete.connect(self._handle_result)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()
        
    def _handle_result(self, result: UpdateCheckResult):
        """Handle version check result from worker."""
        self.last_result = result
        
        if result.state == UpdateState.MANDATORY_UPDATE:
            logger.warning(f"Mandatory update required: {result.latest_version}")
            self.mandatory_update_required.emit(result)
            
        elif result.state == UpdateState.OPTIONAL_UPDATE:
            logger.info(f"Optional update available: {result.latest_version}")
            self.optional_update_available.emit(result)
            
        elif result.state == UpdateState.UP_TO_DATE:
            logger.info("App version is up to date")
            self.up_to_date.emit()
            
        else:
            logger.error(f"Unknown update state: {result.state}")
            self.check_failed.emit("Unknown update state")
            
    def get_last_result(self) -> UpdateCheckResult:
        """Get the last check result (if any)."""
        return self.last_result
