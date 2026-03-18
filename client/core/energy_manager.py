"""
Energy Manager - Usage-Based Licensing System with Server Validation

Manages the daily "Energy" allowance for Free Tier users.
- Secures balance using AES-GCM encryption bound to device ID.
- Syncs with server for job-based validation (optimized for low server load).
- Handles daily refresh logic.
- Calculates costs based on conversion complexity.
"""

import os
import json
import uuid
import base64
import time
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

# Try to import cryptography, fallback to simple obfuscation if missing
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    import hashlib

from PySide6.QtCore import QObject, Signal
from client.core.energy_api_client import EnergyAPIClient

class EnergyManager(QObject):
    """
    Singleton service to manage user 'Energy'.
    
    Persists balance securely to prevent tampering.
    Refreshes balance daily for Free Tier users.
    """
    
    # Signals
    energy_changed = Signal(int, int)  # current, max
    refreshed = Signal()               # emitted on daily reset
    server_sync_failed = Signal(str)   # error message
    
    _instance = None
    
    # Configuration
    DEFAULT_DAILY_ENERGY = 35  # Fallback if server doesn't specify
    STORAGE_FILE = "energy.dat"
    
    # Job-Based Sync Thresholds
    SYNC_THRESHOLD_FREE    = 10  # Free users: reserve with server if job cost > 10
    SYNC_THRESHOLD_PREMIUM = 30  # Premium users: reserve with server if job cost > 30
    
    # Configuration Paths
    CONFIG_DIR = "client/config"
    LAB_CREDITS_FILE = "credits_lab.json"
    PRESETS_CREDITS_FILE = "credits_presets.json"
    
    # Default Fallback Costs (if config missing)
    DEFAULT_COSTS = {
        'image': 1,
        'video': 5,
        'loop': 3
    }
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        super().__init__()
        if EnergyManager._instance is not None:
            raise Exception("EnergyManager is a singleton")
            
        self.storage_path = self._get_storage_path()
        self.key = self._get_device_key()
        
        self.max_daily_energy = self.DEFAULT_DAILY_ENERGY  # Dynamic limit from server
        self.balance = self.max_daily_energy
        self.last_refresh = datetime.utcnow().date().isoformat()
        self.unsynced_usage = 0  # Track local usage not yet reported to server
        self.server_signature = None  # Server's cryptographic signature
        
        # Session state is now managed by SessionManager
        # Access via SessionManager.instance().is_premium, .jwt_token, etc.
        
        # Load credit configurations
        self._lab_credits = {}
        self._preset_credits = {}
        self._load_credit_configs()
        
        # Initialize API client (will be configured with credentials later)
        from client.config.config import API_BASE_URL
        self.api_client = EnergyAPIClient(API_BASE_URL)
        
        # Connect signals
        self.api_client.sync_completed.connect(self._on_sync_completed)
        self.api_client.reservation_completed.connect(self._on_reservation_completed)
        self.api_client.report_completed.connect(self._on_report_completed)
        
        # Batch sync timer - report accumulated usage every 60 seconds
        from PySide6.QtCore import QTimer
        self._batch_timer = QTimer()
        self._batch_timer.timeout.connect(self._flush_unsynced_usage)
        self._batch_timer.start(60000)  # 60 seconds
        
        self.load()
        self.check_refresh()
        
    def _load_credit_configs(self):
        """Load credit pricing rules from JSON files."""
        try:
            # Determine config directory
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # Production: Load from bundled assets
                config_dir = Path(sys._MEIPASS) / "client" / "config"
            else:
                # Development: Load from source
                config_dir = Path(self.CONFIG_DIR)
                
            # Load Lab Credits
            lab_path = config_dir / self.LAB_CREDITS_FILE
            if lab_path.exists():
                with open(lab_path, 'r') as f:
                    self._lab_credits = json.load(f)
                print(f"[EnergyManager] Loaded Lab credits from {lab_path}")
            else:
                print(f"[EnergyManager] Warning: Lab credits file not found at {lab_path}")
                
            # Load Preset Credits
            preset_path = config_dir / self.PRESETS_CREDITS_FILE
            if preset_path.exists():
                with open(preset_path, 'r') as f:
                    self._preset_credits = json.load(f)
                print(f"[EnergyManager] Loaded Preset credits from {preset_path}")
            else:
                print(f"[EnergyManager] Warning: Preset credits file not found at {preset_path}")
                
        except Exception as e:
            print(f"[EnergyManager] Error loading credit configs: {e}")

    def _get_storage_path(self):
        """Get path to storage file in user app data"""
        # Ensure directory exists in user profile to prevent UAC PermissionErrors
        import os
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        path = Path(app_data) / 'wexporting' / 'config'
        path.mkdir(parents=True, exist_ok=True)
        return path / self.STORAGE_FILE

    def _get_device_key(self):
        """
        Generate encryption key for local storage.
        
        NOTE: This is NOT for authentication. Store authentication
        is handled by IStoreAuthProvider. This key is only for
        encrypting the local energy.dat file.
        """
        # Use a fixed application-specific key for encryption
        # This prevents casual tampering but is not a security boundary
        # (real security is server-side via JWT validation)
        app_secret = "imgapp_energy_v1"
        if CRYPTO_AVAILABLE:
            import hashlib
            key_hash = hashlib.sha256(app_secret.encode()).digest()
            return key_hash
        else:
            return app_secret

    def load(self):
        """Load and decrypt energy state"""
        if not self.storage_path.exists():
            self.reset_defaults()
            return
            
        try:
            with open(self.storage_path, 'rb') as f:
                data = f.read()
                
            if CRYPTO_AVAILABLE:
                # Format: [Nonce 12 bytes][Ciphertext][Tag 16 bytes (implicit)]
                # AESGCM in cryptography lib handles tag automatically appended
                nonce = data[:12]
                ciphertext = data[12:]
                aesgcm = AESGCM(self.key)
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                state = json.loads(plaintext.decode())
            else:
                # Fallback: Base64 decode + simple XOR check (not secure, just obfuscated)
                # In real prod, force cryptography lib
                encoded = base64.b64decode(data).decode()
                # Split signature
                content, sig = encoded.rsplit(':', 1)
                
                # Verify binding
                expected_sig = hashlib.sha256((content + self.key).encode()).hexdigest()[:8]
                if sig != expected_sig:
                    raise ValueError("Tampered data")
                state = json.loads(content)
            
            self.balance = state.get('balance', self.max_daily_energy)
            self.last_refresh = state.get('last_refresh', datetime.utcnow().date().isoformat())
            self.max_daily_energy = state.get('max_daily_energy', self.DEFAULT_DAILY_ENERGY)
            
        except Exception as e:
            print(f"[EnergyManager] Failed to load data (tampering?): {e}")
            self.reset_defaults()
            
    def save(self):
        """Encrypt and save energy state"""
        state = {
            'balance': self.balance,
            'last_refresh': self.last_refresh,
            'max_daily_energy': self.max_daily_energy
        }
        json_str = json.dumps(state)
        
        try:
            if CRYPTO_AVAILABLE:
                aesgcm = AESGCM(self.key)
                nonce = os.urandom(12)
                ciphertext = aesgcm.encrypt(nonce, json_str.encode(), None)
                # Write Nonce + Ciphertext (Tag is included in ciphertext by library)
                with open(self.storage_path, 'wb') as f:
                    f.write(nonce + ciphertext)
            else:
                # Fallback
                sig = hashlib.sha256((json_str + self.key).encode()).hexdigest()[:8]
                content = f"{json_str}:{sig}"
                with open(self.storage_path, 'wb') as f:
                    f.write(base64.b64encode(content.encode()))
        except Exception as e:
            print(f"[EnergyManager] Failed to save: {e}")

    def reset_defaults(self):
        """Reset to default max energy"""
        self.balance = self.max_daily_energy
        self.last_refresh = datetime.utcnow().date().isoformat()
        self.save()
        self.energy_changed.emit(self.balance, self.max_daily_energy)

    def check_refresh(self):
        """Check if day has changed (UTC) and refresh if needed"""
        today = datetime.utcnow().date().isoformat()
        if self.last_refresh != today:
            print(f"[EnergyManager] New UTC day! Refreshing energy. Last: {self.last_refresh}, Today: {today}")
            self.balance = self.max_daily_energy
            self.last_refresh = today
            self.save()
            self.refreshed.emit()
            self.energy_changed.emit(self.balance, self.max_daily_energy)

    def get_balance(self):
        self.check_refresh() # Ensure fresh
        return self.balance

    def can_afford(self, cost):
        """Check if user can afford cost"""
        return self.get_balance() >= cost

    def consume(self, cost):
        """Deduct energy locally (for small jobs)"""
        if self.can_afford(cost):
            self.balance -= cost
            self.unsynced_usage += cost
            self.save()
            self.energy_changed.emit(self.balance, self.max_daily_energy)
            return True
        return False
    
    def request_job_energy(self, cost, conversion_type="unknown", params=None):
        """
        Request energy for a job. Uses job-based logic:
        - If cost > threshold: Reserve with server (blocks until response)
        - If cost <= threshold: Deduct locally
        
        Returns: True if approved, False if insufficient
        """
        from client.core.session_manager import SessionManager
        session = SessionManager.instance()
        is_premium = session.is_premium

        # Choose threshold by tier
        threshold = self.SYNC_THRESHOLD_PREMIUM if is_premium else self.SYNC_THRESHOLD_FREE

        # Small job: deduct locally (premium jobs under 30, free jobs under 10)
        if cost <= threshold:
            if is_premium:
                return True  # Premium small jobs — no local balance tracking needed
            return self.consume(cost)

        # Large job: reserve with server using JWT
        jwt_token = session.jwt_token
        
        if not jwt_token:
            print("[EnergyManager] No JWT token - falling back to local balance check for large job")
            # Fall back to local check (no server validation)
            return self.consume(cost)
        
        if self.api_client.offline_mode:
            print("[EnergyManager] Offline mode - falling back to local balance check for large job")
            return self.consume(cost)
        
        # Configure API client with JWT
        self.api_client.set_jwt_token(jwt_token)
        
        # Trigger reservation (async via signal)
        self.api_client.reserve_energy(cost)
        
        # Note: This is now async - result comes via _on_reservation_completed
        # For blocking behavior, conversion_conductor needs to wait for signal
        print(f"[EnergyManager] Requesting server reservation for {cost} energy...")
        return True  # Optimistic - will be corrected by signal if fails

    def calculate_cost(self, conversion_type, params=None):
        """
        Calculate energy cost based on conversion parameters and mode (Lab vs Preset).
        
        Args:
            conversion_type (str): 'image', 'video', 'gif', 'loop'
            params (dict): Conversion parameters from CommandPanel/Preset
        """
        if not params:
            params = {}
            
        # Check if using a preset (Mode-based determination)
        is_preset = params.get('preset_id') is not None
        
        if is_preset:
            return self._calculate_preset_cost(conversion_type, params)
        else:
            return self._calculate_lab_cost(conversion_type, params)

    def _calculate_preset_cost(self, conversion_type, params):
        """Calculate cost for Preset Mode."""
        preset_id = params.get('preset_id')
        
        # 1. YAML Override (Highest Priority)
        # Passed via params from ConversionConductor -> PresetDefinition.credit_cost
        # SECURITY FIX: Ignore credit_cost for user presets to prevent tampering
        if params.get('credit_cost') is not None:
            if not params.get('is_user_preset', False):
                return int(params['credit_cost'])
            
        # 2. Specific Preset Override (Config JSON)
        specific_presets = self._preset_credits.get('specific_presets', {})
        if preset_id in specific_presets:
            return specific_presets[preset_id]
            
        # 3. Category Fallback
        category = params.get('preset_category')
        if category:
            categories_config = self._preset_credits.get('categories', {})
            # Try exact match, then lowercase
            cat_cost = categories_config.get(category) or categories_config.get(category.lower())
            if cat_cost is not None:
                return cat_cost
            
        # 4. Type Fallback (Lowest Priority)
        base_costs = self._preset_credits.get('base_costs', {})
        cost = base_costs.get(f"{conversion_type}_preset", 0)
        
        # Fallback if 0 or missing
        if cost == 0:
            cost = self.DEFAULT_COSTS.get(conversion_type, 1)
            
        # Apply complexity multiplier (if preset params define complexity)
        complexity = params.get('complexity', 'low')
        multipliers = self._preset_credits.get('complexity_multipliers', {})
        multiplier = multipliers.get(complexity, 1.0)
        
        return int(cost * multiplier) or 1

    def _calculate_lab_cost(self, conversion_type, params):
        """Calculate cost for Lab Mode (granular operations)."""
        mode_config = self._lab_credits.get('modes', {}).get(conversion_type, {})
        
        # Determine base cost from format/codec
        cost = 0
        if conversion_type == 'image':
            # Image: lookup by format
            format_name = params.get('format', 'PNG').lower()
            formats = mode_config.get('formats', {})
            cost = formats.get(format_name, mode_config.get('default_format_cost', 1))
        elif conversion_type == 'video':
            # Video: lookup by codec
            codec_raw = params.get('codec', params.get('video_codec', 'MP4 (H.264)'))
            # Normalize: remove periods and convert to lowercase
            # "MP4 (H.264)" -> "mp4 (h264)", "MP4 (H.265)" -> "mp4 (h265)"
            codec = codec_raw.lower().replace('.', '')
            codecs = mode_config.get('codecs', {})
            
            # Match codec with priority order (more specific first)
            # Check h265/hevc before h264 to avoid false matches
            codec_cost = None
            if 'h265' in codec or 'hevc' in codec:
                codec_cost = codecs.get('h265') or codecs.get('hevc')
            elif 'h264' in codec:
                codec_cost = codecs.get('h264')
            elif 'av1' in codec:
                codec_cost = codecs.get('av1')
            elif 'vp9' in codec:
                codec_cost = codecs.get('vp9')
            
            cost = codec_cost if codec_cost is not None else mode_config.get('default_codec_cost', 3)
        elif conversion_type == 'loop':
            # Loop: lookup by format (GIF or WebM with codec)
            # LoopTab sends 'loop_format', but fallback to 'format' for compatibility
            format_name = params.get('loop_format', params.get('format', 'GIF')).lower()
            formats = mode_config.get('formats', {})
            
            # Check if WebM with specific codec
            if 'webm' in format_name:
                # LoopTab sets codec = loop_format (e.g., "WebM (AV1)" or "WebM (VP9)")
                codec_raw = params.get('codec', params.get('webm_codec', ''))
                codec = codec_raw.lower()
                if 'av1' in codec:
                    cost = formats.get('webm_av1', formats.get('webm', mode_config.get('default_format_cost', 5)))
                elif 'vp9' in codec:
                    cost = formats.get('webm_vp9', formats.get('webm', mode_config.get('default_format_cost', 5)))
                else:
                    cost = formats.get('webm', mode_config.get('default_format_cost', 5))
            else:
                cost = formats.get(format_name, mode_config.get('default_format_cost', 5))
        else:
            # Fallback
            cost = self.DEFAULT_COSTS.get(conversion_type, 1)
        
        # Check if Target Size mode is active
        size_mode = params.get('image_size_mode') or params.get('video_size_mode') or params.get('gif_size_mode')
        if size_mode == 'max_size':
            # Add Target Size mode premium
            target_size_cost = mode_config.get('target_size_cost', 0)
            cost += target_size_cost
        
        operations = mode_config.get('operations', {})
        
        # --- Resize Cost ---
        if 'resize' in operations:
            resize_op = operations['resize']
            
            # Check for generic resize mode param
            # Note: Parameter keys differ by tab (image_size_mode, video_size_mode, etc.)
            # But CommandPanel often normalizes or we check specific keys
            
            # Helper to check if resize is actually active
            is_resize_active = False
            resize_mode = params.get('resize_mode', 'No resize')
            
            if resize_mode != 'No resize':
                # Map UI string to config key
                # UI sends: "By width (pixels)", "By longer edge (pixels)", "By ratio (percent)"
                mode_cost = 0
                resize_modes_cost = resize_op.get('modes', {})
                
                resize_lower = resize_mode.lower()
                if 'width' in resize_lower:
                    mode_cost = resize_modes_cost.get('width', 0)
                    is_resize_active = True
                elif 'longer edge' in resize_lower:
                    mode_cost = resize_modes_cost.get('longer_edge', 0)
                    is_resize_active = True
                elif 'ratio' in resize_lower or 'percent' in resize_lower:
                    mode_cost = resize_modes_cost.get('percentage', 0)
                    is_resize_active = True
                elif 'height' in resize_lower:
                    mode_cost = resize_modes_cost.get('width', 0)  # Treat as width/dimension
                    is_resize_active = True
                
                if is_resize_active:
                    cost += resize_op.get('base', 0)
                    cost += mode_cost

        # --- Rotate Cost ---
        if 'rotate' in operations:
            rotate_angle = params.get('rotation_angle')
            # Check if rotation is actually active (not None, not 0, not "No rotation")
            if rotate_angle and rotate_angle != "No rotation":
                try:
                    angle_val = float(rotate_angle)
                    if abs(angle_val) > 0.01: # Account for float precision
                        cost += operations['rotate'].get('base', 0)
                except (ValueError, TypeError):
                    # If it's a string like "90 degrees" or non-numeric but not "No rotation"
                    cost += operations['rotate'].get('base', 0)

        # --- Retime/Time Cost ---
        if 'retime' in operations:
            # Check for time operations
            if params.get('enable_time_cutting') or params.get('retime_enabled'):
                 cost += operations['retime'].get('base', 0)

        return max(1, cost)

    def get_time_until_refresh(self):
        """Return string "HH:MM" until UTC midnight"""
        now_utc = datetime.utcnow()
        # Tomorrow midnight UTC
        tomorrow_midnight = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        remaining = tomorrow_midnight - now_utc
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes}m"
    
    # ===== Store Authentication Integration =====
    
    def set_store_auth(self, store_user_id: str, jwt_token: str, is_premium: bool):
        """
        DEPRECATED: Use SessionManager.instance().start_session() instead.
        Kept for backward compatibility.
        """
        from client.core.session_manager import SessionManager
        session = SessionManager.instance()
        session.start_session(
            store_user_id=store_user_id,
            jwt_token=jwt_token,
            is_premium=is_premium
        )
        
        # Sync with server to get current balance
        if not is_premium:
            self.sync_with_server_jwt()
    
    def sync_with_server_jwt(self):
        """
        Sync balance from server using JWT authentication.
        
        This replaces the old email/license_key authentication.
        Called on app launch after Store login.
        """
        from client.core.session_manager import SessionManager
        jwt_token = SessionManager.instance().jwt_token
        
        if not jwt_token:
            print("[EnergyManager] Cannot sync: No JWT token")
            return
        
        # Configure API client with JWT token
        self.api_client.set_jwt_token(jwt_token)
        
        # Trigger sync (response handled by _on_sync_completed signal)
        self.api_client.sync_balance()
        print(f"[EnergyManager] Syncing with server using JWT authentication...")
    

    
    def set_premium_status(self, is_premium):
        """DEPRECATED: Use SessionManager.instance()._set_premium_status() instead."""
        from client.core.session_manager import SessionManager
        SessionManager.instance()._set_premium_status(is_premium)
    
    # ===== Signal Handlers =====
    
    def _on_sync_completed(self, success, data):
        """Handle sync response from server"""
        if success:
            self.balance = data.get('balance', self.balance)
            # Server returns 'max_daily' (free allowance + purchased_energy)
            self.max_daily_energy = data.get('max_daily', self.DEFAULT_DAILY_ENERGY)
            self.server_signature = data.get('signature')

            # Update premium status from server's is_premium field
            from client.core.session_manager import SessionManager
            is_premium = data.get('is_premium', False)
            SessionManager.instance()._set_premium_status(is_premium)

            print(f"[EnergyManager] Sync successful - Balance: {self.balance}, Max: {self.max_daily_energy}, Premium: {is_premium}")
            self.unsynced_usage = 0
            self.save()
            self.energy_changed.emit(self.balance, self.max_daily_energy)
        else:
            self.server_sync_failed.emit(data.get('error', 'unknown'))
    
    def _on_reservation_completed(self, success, data):
        """Handle reservation response from server"""
        self._pending_reservation = {'success': success, 'data': data}
        if success:
            self.balance = data.get('new_balance', self.balance)
            self.server_signature = data.get('signature')
            self.save()
            self.energy_changed.emit(self.balance, self.max_daily_energy)
    
    def _on_report_completed(self, success, data):
        """Handle report response from server"""
        if success:
            self.balance = data.get('new_balance', self.balance)
            self.server_signature = data.get('signature')
            self.unsynced_usage = 0
            self.save()
            self.energy_changed.emit(self.balance, self.max_daily_energy)
    
    def _flush_unsynced_usage(self):
        """
        Flush accumulated local usage to server (batch sync).
        
        Called every 60 seconds by batch timer.
        Only reports if there's unsynced usage and user is not premium.
        """
        from client.core.session_manager import SessionManager
        session = SessionManager.instance()
        
        # Skip if premium or no unsynced usage
        if session.is_premium or self.unsynced_usage <= 0:
            return
        
        # Skip if no JWT token
        jwt_token = session.jwt_token
        if not jwt_token:
            return
        
        # Configure API client and report usage
        self.api_client.set_jwt_token(jwt_token)
        self.api_client.report_usage(self.unsynced_usage, self.server_signature)
        
        print(f"[EnergyManager] Batch sync: reporting {self.unsynced_usage} energy usage")
