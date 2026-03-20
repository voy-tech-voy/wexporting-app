"""
Update Conductor

Decouples application update logic from MainWindow.
Manages the async UpdateClient using a QThread to prevent UI blocking.
"""

import asyncio
import logging
from PySide6.QtCore import QObject, QThread, Signal
from client.core.update_client import UpdateClient, UpdateManifest
from client.config import config

logger = logging.getLogger(__name__)

class UpdateWorker(QThread):
    """
    Worker thread to execute async update checks.
    """
    check_complete = Signal(bool, object)  # success, manifest/error_msg
    
    def __init__(self, server_url, license_key):
        super().__init__()
        self.server_url = server_url
        self.license_key = license_key
        
    def run(self):
        """Execute update check in asyncio event loop."""
        try:
            # Create usage-specific event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            client = UpdateClient(self.server_url, self.license_key)
            
            # Check for updates
            manifest = loop.run_until_complete(client.check_for_updates())
            
            if manifest:
                # Check if we actually have updates compared to local state
                if manifest.has_updates(client.local_manifest):
                    self.check_complete.emit(True, manifest)
                else:
                    self.check_complete.emit(True, None) # Success, but no updates
            else:
                self.check_complete.emit(False, "Failed to fetch update manifest")
                
            loop.close()
            
        except Exception as e:
            logger.error(f"Update worker failed: {e}")
            self.check_complete.emit(False, str(e))


class UpdateApplyWorker(QThread):
    """
    Worker thread to execute async update application (download and install).
    """
    apply_complete = Signal(bool, object)  # success, result_dict/error_msg
    progress_update = Signal(str, int)  # status_message, percentage
    
    def __init__(self, server_url, license_key, manifest):
        super().__init__()
        self.server_url = server_url
        self.license_key = license_key
        self.manifest = manifest
        
    def run(self):
        """Execute update application in asyncio event loop."""
        try:
            # Create thread-specific event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            client = UpdateClient(self.server_url, self.license_key)
            
            # Emit initial progress
            self.progress_update.emit("Starting update download...", 0)
            
            # Apply all updates
            result = loop.run_until_complete(client.apply_all_updates(self.manifest))
            
            # Emit completion progress
            self.progress_update.emit("Updates applied successfully!", 100)
            
            # Emit success
            self.apply_complete.emit(True, result)
            
            loop.close()
            
        except Exception as e:
            logger.error(f"Update apply worker failed: {e}")
            self.apply_complete.emit(False, str(e))


class UpdateConductor(QObject):
    """
    Coordinator for application updates.
    
    Responsibilities:
    - Manage UpdateWorker thread
    - Provide simple API for MainWindow (check_updates)
    - Emit higher-level signals for UI (updates_available, update_error)
    """
    
    updates_available = Signal(object)  # Emits UpdateManifest
    no_update_found = Signal()
    update_error = Signal(str)
    
    # New signals for update application
    update_progress = Signal(str, int)  # message, percentage
    update_complete = Signal(dict)  # result dictionary
    update_failed = Signal(str)  # error message
    check_already_running = Signal()  # Emitted when check is already in progress
    
    def __init__(self, jwt_token=None):
        super().__init__()
        self.check_worker = None
        self.apply_worker = None
        
        # JWT token for authentication (set via set_auth_token)
        self.jwt_token = jwt_token or "FREE_TIER"  # Fallback for development
        self.server_url = config.API_BASE_URL

    def set_auth_token(self, jwt_token: str):
        """
        Update the JWT token for authentication.
        Should be called after successful store authentication.

        Args:
            jwt_token: JWT token from server after store validation
        """
        self.jwt_token = jwt_token
        logger.info("UpdateConductor: JWT token updated")

    def _get_current_jwt(self) -> str:
        """Get JWT from SessionManager, falling back to stored value."""
        try:
            from client.core.session_manager import get_session_manager
            token = get_session_manager().jwt_token
            if token:
                return token
        except Exception:
            pass
        return self.jwt_token  # fallback (dev mode / "FREE_TIER")

    def check_for_updates(self):
        """
        Start checking for updates in background.
        Does nothing if check is already running.
        """
        if self.check_worker:
            try:
                if self.check_worker.isRunning():
                    logger.info("Update check already in progress")
                    self.check_already_running.emit()
                    return
            except RuntimeError:
                logger.warning("UpdateWorker C++ object was deleted")
                self.check_worker = None

        logger.info("Starting update check...")
        token = self._get_current_jwt()
        self.check_worker = UpdateWorker(self.server_url, token)
        self.check_worker.check_complete.connect(self._handle_check_result)
        self.check_worker.finished.connect(self.check_worker.deleteLater)
        self.check_worker.finished.connect(self._cleanup_check_worker)
        self.check_worker.start()
        
    def apply_updates(self, manifest):
        """
        Start applying updates in background.
        Does nothing if application is already running.
        
        Args:
            manifest: UpdateManifest object with updates to apply
        """
        if self.apply_worker:
            try:
                if self.apply_worker.isRunning():
                    logger.warning("Update application already in progress")
                    return
            except RuntimeError:
                logger.warning("UpdateApplyWorker C++ object was deleted")
                self.apply_worker = None
            
        logger.info("Starting update application...")
        token = self._get_current_jwt()
        self.apply_worker = UpdateApplyWorker(self.server_url, token, manifest)
        self.apply_worker.apply_complete.connect(self._handle_apply_result)
        self.apply_worker.progress_update.connect(self.update_progress.emit)
        self.apply_worker.finished.connect(self.apply_worker.deleteLater)
        self.apply_worker.finished.connect(self._cleanup_apply_worker)
        self.apply_worker.start()
        
    def _cleanup_check_worker(self):
        """Clean up check worker reference when finished."""
        self.check_worker = None
    
    def _cleanup_apply_worker(self):
        """Clean up apply worker reference when finished."""
        self.apply_worker = None
        
    def _handle_check_result(self, success, result):
        """Handle result from check worker thread."""
        if success:
            if result:
                logger.info("Updates found!")
                self.updates_available.emit(result)
            else:
                logger.info("No updates available.")
                self.no_update_found.emit()
        else:
            logger.error(f"Update check error: {result}")
            self.update_error.emit(str(result))
            
    def _handle_apply_result(self, success, result):
        """Handle result from apply worker thread."""
        if success:
            logger.info(f"Updates applied successfully: {result}")
            self.update_complete.emit(result)
        else:
            logger.error(f"Update application failed: {result}")
            self.update_failed.emit(str(result))
