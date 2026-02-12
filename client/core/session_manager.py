"""
Session Manager - Centralized User Session & Entitlements

Manages user identity, authentication tokens, and entitlements (Premium status).
Implements runtime obfuscation for security-sensitive flags.
"""

import os
from PyQt6.QtCore import QObject, pyqtSignal


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
    premium_status_changed = pyqtSignal(bool)  # Emitted when premium status changes
    session_started = pyqtSignal()              # Emitted when user logs in
    session_ended = pyqtSignal()                # Emitted when user logs out
    
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
        
        print("[SessionManager] Session ended")
        self.session_ended.emit()
    
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
