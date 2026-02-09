"""
JWT Authentication Module

Provides JWT token creation, verification, and decorators for protected endpoints.
Replaces admin-key authentication for user-facing endpoints.
"""

import jwt
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from typing import Optional, Dict, Any
from config.settings import Config

logger = logging.getLogger(__name__)


def create_jwt_token(store_user_id: str, platform: str, is_premium: bool = False) -> str:
    """
    Create a JWT token for authenticated store users.
    
    Args:
        store_user_id: Platform-specific user ID (MS SubjectID or Apple SubjectID)
        platform: "msstore" or "appstore"
        is_premium: Whether user has premium entitlement
        
    Returns:
        str: Signed JWT token
    """
    expiry_hours = getattr(Config, 'JWT_EXPIRY_HOURS', 24)
    
    payload = {
        'sub': store_user_id,
        'platform': platform,
        'is_premium': is_premium,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=expiry_hours)
    }
    
    secret_key = Config.JWT_SECRET_KEY or Config.SECRET_KEY
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    
    logger.info(f"Created JWT for user {store_user_id[:8]}... (platform: {platform}, premium: {is_premium})")
    return token


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Decoded token claims, or None if invalid
    """
    try:
        secret_key = Config.JWT_SECRET_KEY or Config.SECRET_KEY
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


def require_jwt(f):
    """
    Decorator to require JWT authentication for endpoints.
    
    Checks Authorization header for Bearer token.
    Adds 'jwt_claims' to request context if valid.
    
    Usage:
        @api_bp.route('/protected')
        @require_jwt
        def protected_endpoint():
            user_id = request.jwt_claims['sub']
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract token from Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'success': False,
                'error': 'missing_auth_header',
                'message': 'Authorization header required'
            }), 401
        
        # Parse Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({
                'success': False,
                'error': 'invalid_auth_header',
                'message': 'Authorization header must be "Bearer <token>"'
            }), 401
        
        token = parts[1]
        
        # Verify token
        claims = verify_jwt_token(token)
        if not claims:
            return jsonify({
                'success': False,
                'error': 'invalid_token',
                'message': 'Invalid or expired JWT token'
            }), 401
        
        # Attach claims to request context
        request.jwt_claims = claims
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_current_user_id() -> Optional[str]:
    """
    Get the current authenticated user ID from request context.
    
    Returns:
        str: User ID from JWT claims, or None if not authenticated
    """
    if hasattr(request, 'jwt_claims'):
        return request.jwt_claims.get('sub')
    return None


def is_premium_user() -> bool:
    """
    Check if current user has premium entitlement.
    
    Returns:
        bool: True if user is premium
    """
    if hasattr(request, 'jwt_claims'):
        return request.jwt_claims.get('is_premium', False)
    return False
