"""
Client-side Message Manager
Fetches and caches messages from the server
Falls back to hardcoded messages if server is unavailable
"""
import requests
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MessageManager:
    """
    Manages message fetching and caching from the server.
    Provides fallback to hardcoded messages if server is unavailable.
    """
    
    def __init__(self, server_url: str, cache_file: str = "message_cache.json"):
        self.server_url = server_url.rstrip('/')
        self.cache_file = Path(cache_file)
        self.messages = {}
        self.fallback_messages = self._get_fallback_messages()
        self._load_cache()
    
    def _get_fallback_messages(self) -> Dict[str, Any]:
        """
        Hardcoded fallback messages if server is unavailable
        These should mirror the server/messages.py structure
        """
        return {
            "server_health": {
                "online": {
                    "title": "Connected",
                    "message": "Successfully connected to license server.",
                    "action": None
                },
                "offline": {
                    "title": "Server Offline",
                    "message": "Cannot connect to license server.\n\nACTION: Check your internet connection and try again. If the problem persists, try again later.",
                    "action": "Check your internet connection and try again."
                },
                "timeout": {
                    "title": "Connection Timeout",
                    "message": "The server is taking too long to respond.\n\nACTION: The server might be experiencing high traffic. Please try again in a few moments.",
                    "action": "Try again in a few moments."
                },
                "slow": {
                    "title": "Slow Response",
                    "message": "The server is responding slowly.\n\nACTION: You can continue, but some operations may take longer than usual.",
                    "action": "Operations may take longer than usual."
                },
                "maintenance": {
                    "title": "Under Maintenance",
                    "message": "The license server is currently under maintenance.\n\nACTION: Please try again later. We apologize for the inconvenience.",
                    "action": "Try again later."
                },
                "overloaded": {
                    "title": "Server Overloaded",
                    "message": "The server is currently experiencing high traffic.\n\nACTION: Please wait a moment and try again.",
                    "action": "Wait a moment and try again."
                },
                "circuit_open": {
                    "title": "Connection Issues",
                    "message": "We're having trouble connecting to the license server.\n\nACTION: The connection will be retried automatically. You can continue working in offline mode if you have a valid license.",
                    "action": "Connection will be retried automatically."
                }
            },
            "login": {
                "success": {
                    "title": "Welcome Back!",
                    "message": "Successfully logged in with your license.",
                    "action": None
                },
                "email_mismatch": {
                    "title": "Email Mismatch",
                    "message": "The email you entered doesn't match the license.\n\nACTION: Please use the email address associated with your purchase.",
                    "action": "Use your purchase email."
                },
                "license_expired": {
                    "title": "License Expired",
                    "message": "Your license has expired on {expiry_date}.\n\nACTION: Please renew your license to continue using the app.",
                    "action": "Renew your license."
                },
                "invalid_license": {
                    "title": "Invalid License",
                    "message": "The license key you entered is not valid.\n\nACTION: Please check your email for the correct license key or contact support.",
                    "action": "Check your license key."
                },
                "server_error": {
                    "title": "Server Error",
                    "message": "We encountered an error while verifying your license.\n\nACTION: Please try again later or contact support if the problem persists.",
                    "action": "Try again later."
                }
            },
            "general": {
                "error": {
                    "title": "Error",
                    "message": "An unexpected error occurred: {error}\n\nACTION: Please try again or contact support if the problem persists.",
                    "action": "Try again or contact support."
                },
                "success": {
                    "title": "Success",
                    "message": "{message}",
                    "action": None
                },
                "info": {
                    "title": "Information",
                    "message": "{message}",
                    "action": None
                },
                "warning": {
                    "title": "Warning",
                    "message": "{message}\n\nACTION: {action}",
                    "action": "{action}"
                }
            }
        }
    
    def _load_cache(self):
        """Load messages from local cache if available"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.messages = json.load(f)
                logger.info("Loaded messages from cache")
            else:
                self.messages = self.fallback_messages.copy()
                logger.info("Using fallback messages (no cache found)")
        except Exception as e:
            logger.error(f"Error loading message cache: {e}")
            self.messages = self.fallback_messages.copy()
    
    def _save_cache(self):
        """Save messages to local cache"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, indent=2, ensure_ascii=False)
            logger.info("Saved messages to cache")
        except Exception as e:
            logger.error(f"Error saving message cache: {e}")
    
    def fetch_from_server(self, timeout: int = 5) -> bool:
        """
        Fetch messages from server and update cache
        Returns True if successful, False otherwise
        """
        try:
            url = f"{self.server_url}/api/v1/messages"
            logger.info(f"Fetching messages from {url}")
            
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                self.messages = data.get("messages", {})
                self._save_cache()
                logger.info("Successfully fetched and cached messages from server")
                return True
            else:
                logger.warning(f"Server returned error: {data.get('error')}")
                return False
                
        except requests.Timeout:
            logger.warning("Timeout while fetching messages from server")
            return False
        except requests.RequestException as e:
            logger.warning(f"Error fetching messages from server: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error fetching messages: {e}")
            return False
    
    def get_message(self, category: str, key: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Get a specific message by category and key
        Supports variable substitution with kwargs
        
        Args:
            category: Message category (e.g., 'server_health', 'login')
            key: Message key within category (e.g., 'offline', 'success')
            **kwargs: Variables to substitute in message (e.g., email='test@example.com')
        
        Returns:
            Dict with 'title', 'message', 'action' keys, or None if not found
        """
        try:
            message = self.messages.get(category, {}).get(key)
            
            if message is None:
                logger.warning(f"Message not found: {category}.{key}, using fallback")
                message = self.fallback_messages.get(category, {}).get(key)
            
            if message is None:
                logger.error(f"Message not found in fallback either: {category}.{key}")
                return None
            
            # Create a copy to avoid modifying cached message
            result = message.copy()
            
            # Substitute variables if provided
            if kwargs:
                for field in ['title', 'message', 'action']:
                    if result.get(field):
                        try:
                            result[field] = result[field].format(**kwargs)
                        except KeyError as e:
                            logger.warning(f"Missing variable {e} for {category}.{key}.{field}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting message {category}.{key}: {e}")
            return None
    
    def get_category(self, category: str) -> Optional[Dict[str, Any]]:
        """Get all messages for a specific category"""
        messages = self.messages.get(category)
        if messages is None:
            logger.warning(f"Category not found: {category}, using fallback")
            messages = self.fallback_messages.get(category)
        return messages
    
    def refresh(self, timeout: int = 5) -> bool:
        """
        Refresh messages from server
        Falls back to cache/hardcoded if server unavailable
        """
        success = self.fetch_from_server(timeout)
        if not success:
            logger.info("Using cached/fallback messages due to server fetch failure")
        return success


# Global instance (can be initialized once in main.py)
_message_manager_instance = None

def get_message_manager(server_url: str = None) -> MessageManager:
    """
    Get or create the global MessageManager instance
    
    Args:
        server_url: Server URL (required on first call)
    """
    global _message_manager_instance
    
    if _message_manager_instance is None:
        if server_url is None:
            raise ValueError("server_url is required on first call to get_message_manager")
        _message_manager_instance = MessageManager(server_url)
    
    return _message_manager_instance
