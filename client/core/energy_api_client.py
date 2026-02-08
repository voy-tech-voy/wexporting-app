import requests
import time
import json
import logging
import hmac
import hashlib
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# Configure logging
logger = logging.getLogger("EnergyAPIClient")

class EnergyAPIClient(QObject):
    """
    Client for communicating with the Energy Server.
    Handles:
    - Syncing balance on startup
    - Reserving energy for large jobs
    - Reporting usage for small jobs (batching)
    - Verifying server signatures
    """
    
    # Signals
    sync_completed = pyqtSignal(bool, dict) # success, data (balance, max_daily)
    reservation_completed = pyqtSignal(bool, dict) # success, data (approved, new_balance)
    report_completed = pyqtSignal(bool, dict) # success, data (new_balance)
    
    def __init__(self, api_base_url, secret_key=None):
        super().__init__()
        self.base_url = api_base_url
        self.secret_key = secret_key
        self.session = requests.Session()
        self.offline_mode = False
        self.jwt_token = None  # JWT token for authentication
        
        # Endpoints
        self.url_sync = f"{self.base_url}/api/v1/energy/sync"
        self.url_reserve = f"{self.base_url}/api/v1/energy/reserve"
        self.url_report = f"{self.base_url}/api/v1/energy/report"
    
    def set_jwt_token(self, jwt_token: str):
        """Set JWT token for authentication."""
        self.jwt_token = jwt_token
        # Update session headers with Bearer token
        if jwt_token:
            self.session.headers.update({"Authorization": f"Bearer {jwt_token}"})
        else:
            self.session.headers.pop("Authorization", None)
        
    def set_offline_mode(self, enabled):
        """Enable or disable offline mode (grace period)"""
        self.offline_mode = enabled
        
    def sync_balance(self):
        """
        Fetch current energy balance from server using JWT authentication.
        Use this on app launch after Store login.
        """
        if self.offline_mode:
            self.sync_completed.emit(False, {"error": "offline"})
            return
        
        if not self.jwt_token:
            logger.error("Cannot sync: No JWT token set")
            self.sync_completed.emit(False, {"error": "no_jwt_token"})
            return

        try:
            # JWT token is automatically included via session headers
            response = self.session.post(self.url_sync, json={}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if self._verify_signature(data):
                    self.sync_completed.emit(True, data)
                else:
                    logger.warning("Server signature verification failed during sync")
                    self.sync_completed.emit(False, {"error": "signature_mismatch"})
            elif response.status_code == 401:
                self.sync_completed.emit(False, {"error": "unauthorized"})
            else:
                self.sync_completed.emit(False, {"error": f"server_error_{response.status_code}"})
                
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self.sync_completed.emit(False, {"error": str(e)})

    def reserve_energy(self, amount):
        """
        Reserve energy for a large job using JWT authentication.
        Server verifies balance and deducts immediately.
        """
        if self.offline_mode:
            # In offline mode, we can't reserve. Fail unless grace period allows.
            self.reservation_completed.emit(False, {"error": "offline"})
            return
        
        if not self.jwt_token:
            logger.error("Cannot reserve: No JWT token set")
            self.reservation_completed.emit(False, {"error": "no_jwt_token"})
            return

        try:
            # JWT token is automatically included via session headers
            response = self.session.post(self.url_reserve, json={
                "amount": amount
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if self._verify_signature(data):
                    self.reservation_completed.emit(True, data)
                else:
                    self.reservation_completed.emit(False, {"error": "signature_mismatch"})
            else:
                # Handle 402 Payment Required (Insufficient Energy)
                if response.status_code == 402:
                    self.reservation_completed.emit(False, {"error": "insufficient_energy"})
                elif response.status_code == 401:
                    self.reservation_completed.emit(False, {"error": "unauthorized"})
                else:
                    self.reservation_completed.emit(False, {"error": f"server_error_{response.status_code}"})
                    
        except Exception as e:
            self.reservation_completed.emit(False, {"error": str(e)})

    def report_usage(self, usage_amount, last_signature):
        """
        Report accumulated local usage (batching) using JWT authentication.
        Sent on app exit or threshold reach.
        """
        if self.offline_mode:
            # Queue for later? For now just fail gracefully
            self.report_completed.emit(False, {"error": "offline"})
            return
        
        if not self.jwt_token:
            logger.error("Cannot report usage: No JWT token set")
            self.report_completed.emit(False, {"error": "no_jwt_token"})
            return

        try:
            # JWT token is automatically included via session headers
            response = self.session.post(self.url_report, json={
                "usage": usage_amount,
                "last_signature": last_signature
            }, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if self._verify_signature(data):
                    self.report_completed.emit(True, data)
                else:
                    self.report_completed.emit(False, {"error": "signature_mismatch"})
            elif response.status_code == 401:
                self.report_completed.emit(False, {"error": "unauthorized"})
            else:
                self.report_completed.emit(False, {"error": f"server_error_{response.status_code}"})
                
        except Exception as e:
            self.report_completed.emit(False, {"error": str(e)})

    def _verify_signature(self, data):
        """
        Verify HMAC signature from server.
        Prevents replay attacks or tampered responses.
        """
        if not self.secret_key:
            return True # Dev mode or no secret set
            
        server_sig = data.get("signature")
        if not server_sig:
            return False
            
        # Reconstruct payload for signing (implementation depends on server agreement)
        # Simple example: balance + timestamp
        payload = f"{data.get('balance')}:{data.get('timestamp')}"
        expected_sig = hmac.new(
            self.secret_key.encode(), 
            payload.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        # Use constant time comparison
        return hmac.compare_digest(server_sig, expected_sig)

