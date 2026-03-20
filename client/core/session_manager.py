"""
Session Manager - Centralized User Session & Entitlements

Manages user identity, authentication tokens, and entitlements (Premium status).
Implements runtime obfuscation for security-sensitive flags.
"""

import os
import base64
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class SessionManager(QObject):
    """
    Singleton manager for user session state and entitlements.
    
    Responsibilities:
    - Store user identity (Store User ID, JWT Token)
    - Manage entitlements (Premium status)
    - Provide secure storage with runtime obfuscation
    - Emit signals when session state changes
    """
    
    # Signals
    premium_status_changed = Signal(bool)  # Emitted when premium status changes
    session_started = Signal()              # Emitted when user logs in
    session_ended = Signal()                # Emitted when user logs out
    
    _instance = None
    
    @classmethod
    def instance(cls):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        super().__init__()
        if SessionManager._instance is not None:
            raise Exception("SessionManager is a singleton. Use SessionManager.instance()")
        
        # Generate runtime obfuscation key (random per session)
        self._obf_key = int.from_bytes(os.urandom(4), 'big')
        
        # Session state (obfuscated)
        self._premium_obf = self._obfuscate(False)  # Obfuscated premium status
        self._store_user_id = None
        self._jwt_token = None
        self._is_authenticated = False
        
        # Path for persisted JWT (same folder as energy.dat)
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        self._session_file = Path(app_data) / 'wexporting' / 'config' / 'session.dat'
    
    def _obfuscate(self, value: bool) -> int:
        """Obfuscate a boolean value using XOR with runtime key."""
        return (1 if value else 0) ^ self._obf_key
    
    def _deobfuscate(self, obf_value: int) -> bool:
        """Deobfuscate a value back to boolean."""
        return bool((obf_value ^ self._obf_key) & 1)
    
    # ===== Premium Status =====
    
    @property
    def is_premium(self) -> bool:
        """Get premium status (deobfuscated)."""
        return self._deobfuscate(self._premium_obf)
    
    def _set_premium_status(self, is_premium: bool):
        """
        Set premium status (INTERNAL USE ONLY).
        
        Args:
            is_premium: True if user has premium entitlement
        """
        old_status = self.is_premium
        self._premium_obf = self._obfuscate(is_premium)
        
        if old_status != is_premium:
            logger.info(f"Premium status changed: {is_premium}")
            from client.config.config import Config
            if Config.DEVELOPMENT_MODE:
                print(f"[SessionManager] Premium status changed: {is_premium}")
            self.premium_status_changed.emit(is_premium)
    
    # ===== Authentication =====
    
    def start_session(self, store_user_id: str, jwt_token: str, is_premium: bool):
        """
        Initialize user session after successful authentication.
        
        Args:
            store_user_id: Platform-specific user ID (MS Store, Apple, etc.)
            jwt_token: JWT token from server
            is_premium: Premium entitlement status
        """
        self._store_user_id = store_user_id
        self._jwt_token = jwt_token
        self._is_authenticated = True
        
        # Set premium status (will emit signal if changed)
        self._set_premium_status(is_premium)
        
        logger.info(f"Session started. User: {store_user_id[:8]}..., Premium: {is_premium}")
        from client.config.config import Config
        if Config.DEVELOPMENT_MODE:
            print(f"[SessionManager] Session started for user: {store_user_id[:8]}... (Premium: {is_premium})")
        self.session_started.emit()
    
    def end_session(self):
        """Clear session state (logout)."""
        self._store_user_id = None
        self._jwt_token = None
        self._is_authenticated = False
        self._set_premium_status(False)
        
        # Clear persisted JWT so next launch starts fresh
        self._clear_persisted_jwt()
        
        logger.info("Session ended")
        self.session_ended.emit()
    
    def set_jwt_token(self, token: str):
        """
        Inject a JWT token into the live session (e.g. from persisted storage).
        Does not emit session_started — only updates the token.
        """
        self._jwt_token = token
    
    def persist_jwt(self, token: str):
        """
        Persist the JWT token to disk so it survives app restarts.
        
        Storage: %APPDATA%/wexporting/config/session.dat
        Format: base64-encoded token (obfuscation only, not encryption).
        Real security is the server-side JWT signature validation.
        """
        if not token:
            return
        try:
            self._session_file.parent.mkdir(parents=True, exist_ok=True)
            encoded = base64.b64encode(token.encode('utf-8'))
            with open(self._session_file, 'wb') as f:
                f.write(encoded)
            logger.info("JWT token persisted to disk")
            from client.config.config import Config
            if Config.DEVELOPMENT_MODE:
                print(f"[SessionManager] JWT persisted to disk")
        except Exception as e:
            logger.error(f"Failed to persist JWT: {e}")
            print(f"[SessionManager] Failed to persist JWT: {e}")
    
    def load_persisted_jwt(self):
        """
        Load a previously persisted JWT from disk.
        
        Returns:
            str: The JWT token, or None if not found / corrupt.
        """
        if not self._session_file.exists():
            return None
        try:
            with open(self._session_file, 'rb') as f:
                encoded = f.read()
            token = base64.b64decode(encoded).decode('utf-8')
            logger.info("Persisted JWT loaded from disk")
            from client.config.config import Config
            if Config.DEVELOPMENT_MODE:
                print(f"[SessionManager] Loaded persisted JWT from disk")
            return token if token else None
        except Exception as e:
            logger.error(f"Failed to load persisted JWT: {e}")
            print(f"[SessionManager] Failed to load persisted JWT: {e}")
            return None
    
    def _clear_persisted_jwt(self):
        """Delete the persisted JWT file (called on logout)."""
        try:
            if self._session_file.exists():
                self._session_file.unlink()
                logger.info("Persisted JWT cleared")
        except Exception as e:
            logger.error(f"Failed to clear persisted JWT: {e}")
            print(f"[SessionManager] Failed to clear persisted JWT: {e}")
    
    # ===== Getters =====
    
    @property
    def store_user_id(self) -> str:
        """Get store user ID."""
        return self._store_user_id
    
    @property
    def jwt_token(self) -> str:
        """Get JWT authentication token."""
        return self._jwt_token
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self._is_authenticated
    
    # ===== Debug =====
    
    def get_session_info(self) -> dict:
        """Get session information for debugging."""
        return {
            'authenticated': self.is_authenticated,
            'premium': self.is_premium,
            'user_id': self.store_user_id[:8] + '...' if self.store_user_id else None
        }
