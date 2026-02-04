"""
Server Health Monitoring System

Implements Circuit Breaker Pattern (used by Netflix, Amazon, Microsoft)
to handle server failures gracefully and provide user-friendly messages.
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional

logger = logging.getLogger(__name__)

# Import MessageManager for centralized messages
try:
    from .message_manager import get_message_manager
    MESSAGE_MANAGER_AVAILABLE = True
except ImportError:
    MESSAGE_MANAGER_AVAILABLE = False
    logger.warning("MessageManager not available, using hardcoded messages")


class ServerHealthChecker:
    """
    Monitor server health and provide user-friendly error messages
    
    Features:
    - Circuit breaker pattern (stops trying after repeated failures)
    - Response time monitoring
    - User-friendly error messages
    - Automatic retry logic
    """
    
    def __init__(self):
        self.last_check = None
        self.last_status = None
        self.consecutive_failures = 0
        self.circuit_open = False  # Circuit breaker state
        self.last_response_time = None
        
        # Circuit breaker thresholds
        self.max_failures = 3  # Open circuit after 3 failures
        self.circuit_timeout = 30  # Seconds before trying again
        self.circuit_opened_at = None
    
    def check_server_health(self, base_url: str, timeout: int = 5) -> Tuple[str, str]:
        """
        Check if server is responsive
        
        Args:
            base_url: Base URL of the server
            timeout: Request timeout in seconds
        
        Returns:
            Tuple of (status, details):
            - status: 'online', 'slow', 'offline', 'maintenance', 'overloaded', 'circuit_open'
            - details: Detailed message about the status
        """
        # Check if circuit breaker is open
        if self.circuit_open:
            # Check if timeout has elapsed
            if self.circuit_opened_at:
                elapsed = (datetime.now() - self.circuit_opened_at).total_seconds()
                if elapsed < self.circuit_timeout:
                    return 'circuit_open', f"Server unavailable. Retry in {int(self.circuit_timeout - elapsed)}s"
                else:
                    # Timeout elapsed, try again (half-open state)
                    logger.info("[SYNC] Circuit breaker timeout elapsed, attempting reconnection...")
                    self.circuit_open = False
        
        try:
            # Try status endpoint
            start_time = datetime.now()
            response = requests.get(
                f"{base_url}/api/v1/status",
                timeout=timeout
            )
            response_time = (datetime.now() - start_time).total_seconds()
            self.last_response_time = response_time
            
            # Update check time
            self.last_check = datetime.now()
            
            if response.status_code == 200:
                # Success - reset failure counter and close circuit
                self.consecutive_failures = 0
                self.circuit_open = False
                self.circuit_opened_at = None
                self.last_status = 'online'
                
                if response_time > 3:
                    return 'slow', f"Server responding slowly ({response_time:.1f}s)"
                return 'online', "Server online and responsive"
            
            elif response.status_code == 503:
                self.consecutive_failures += 1
                self.last_status = 'maintenance'
                return 'maintenance', "Server under maintenance"
            
            elif response.status_code == 429:
                self.consecutive_failures += 1
                self.last_status = 'overloaded'
                return 'overloaded', "Server temporarily overloaded"
            
            else:
                self.consecutive_failures += 1
                self._check_circuit_breaker()
                self.last_status = 'error'
                return 'error', f"Server error (HTTP {response.status_code})"
        
        except requests.exceptions.Timeout:
            self.consecutive_failures += 1
            self._check_circuit_breaker()
            self.last_status = 'timeout'
            return 'timeout', f"Server not responding (timeout after {timeout}s)"
        
        except requests.exceptions.ConnectionError:
            self.consecutive_failures += 1
            self._check_circuit_breaker()
            self.last_status = 'offline'
            
            if self.circuit_open:
                return 'circuit_open', "Server offline (connection failed repeatedly)"
            
            return 'offline', "Cannot connect to server"
        
        except Exception as e:
            self.consecutive_failures += 1
            self._check_circuit_breaker()
            self.last_status = 'unknown'
            return 'unknown', f"Unknown error: {str(e)}"
    
    def _check_circuit_breaker(self):
        """Check if circuit breaker should be opened"""
        if self.consecutive_failures >= self.max_failures and not self.circuit_open:
            self.circuit_open = True
            self.circuit_opened_at = datetime.now()
            logger.warning(
                f"[WARN]  Circuit breaker opened after {self.consecutive_failures} failures. "
                f"Will retry in {self.circuit_timeout}s"
            )
    
    def get_user_message(self, status: str, details: str) -> Dict[str, str]:
        """
        Convert technical status to user-friendly message
        Uses MessageManager if available, falls back to hardcoded messages
        
        Returns:
            Dictionary with 'title', 'message', and 'action' keys
            Action is now included in the main message as bold/prominent text
        """
        # Try to use MessageManager for centralized messages
        if MESSAGE_MANAGER_AVAILABLE:
            try:
                msg_manager = get_message_manager()
                
                # Map status to message keys
                status_map = {
                    'online': 'online',
                    'slow': 'slow',
                    'maintenance': 'maintenance',
                    'overloaded': 'overloaded',
                    'offline': 'offline',
                    'timeout': 'timeout',
                    'circuit_open': 'circuit_open'
                }
                
                key = status_map.get(status)
                if key:
                    message = msg_manager.get_message('server_health', key, details=details)
                    if message:
                        return message
            except Exception as e:
                logger.warning(f"Error getting message from MessageManager: {e}, using fallback")
        
        # Fallback to hardcoded messages
        messages = {
            'online': {
                'title': '[OK] Connected',
                'message': 'Server is online and responsive.',
                'action': None
            },
            'slow': {
                'title': '[WARN] Slow Connection',
                'message': f'{details}\n\nYour request may take longer than usual.\n\n'
                          f'ACTION: Continue anyway',
                'action': None
            },
            'maintenance': {
                'title': '[TOOL] Maintenance Mode',
                'message': 'The server is currently under maintenance.\n\n'
                          f'This usually takes only a few minutes.\n\n'
                          f'ACTION: Retry in 5 minutes',
                'action': None
            },
            'overloaded': {
                'title': '🚦 Server Busy',
                'message': 'The server is handling many requests right now.\n\n'
                          f'Please wait a moment and try again.\n\n'
                          f'ACTION: Retry in 30 seconds',
                'action': None
            },
            'offline': {
                'title': '[X] Server Offline',
                'message': f'{details}\n\n'
                          f'Possible reasons:\n'
                          f'• Server maintenance\n'
                          f'• Your internet connection is down\n'
                          f'• Temporary server overload\n'
                          f'• Firewall blocking connection\n\n'
                          f'ACTION: Check internet connection and try again',
                'action': None
            },
            'timeout': {
                'title': '[TIME]️ Connection Timeout',
                'message': f'The server is not responding.\n\n{details}\n\n'
                          f'This may be temporary. Please check:\n'
                          f'• Your internet connection\n'
                          f'• Firewall settings\n\n'
                          f'ACTION: Try again in a moment',
                'action': None
            },
            'circuit_open': {
                'title': '🔌 Connection Failed',
                'message': f'{details}\n\n'
                          f'The app has stopped trying to connect after multiple failures.\n\n'
                          f'This protects both your computer and the server.\n\n'
                          f'ACTION: Wait and try again',
                'action': None
            },
            'unknown': {
                'title': '[WARN] Unknown Error',
                'message': f'{details}\n\nAn unexpected error occurred.\n\n'
                          f'ACTION: Please contact support if this persists',
                'action': None
            }
        }
        
        return messages.get(status, {
            'title': '[WARN] Connection Issue',
            'message': f'{details}\n\nACTION: Please try again later',
            'action': None
        })
    
    def reset_circuit(self):
        """Manually reset circuit breaker (for admin use)"""
        self.circuit_open = False
        self.circuit_opened_at = None
        self.consecutive_failures = 0
        logger.info("[SYNC] Circuit breaker manually reset")


# Convenience function
def check_server(base_url: str) -> Tuple[bool, Dict[str, str]]:
    """
    Quick server check with user-friendly message
    
    Args:
        base_url: Server base URL
    
    Returns:
        Tuple of (is_online: bool, message_info: dict)
    """
    checker = ServerHealthChecker()
    status, details = checker.check_server_health(base_url)
    message_info = checker.get_user_message(status, details)
    
    is_online = status == 'online'
    
    return is_online, message_info
