"""
App Configuration API Endpoint

Provides version information and update URLs for the Version Gateway Pattern.
Public endpoint (no authentication required) to support update checks for all users.
"""
from flask import jsonify, request
import logging
import json
import os
from . import api_bp

logger = logging.getLogger(__name__)


def load_app_versions():
    """
    Load app version configuration from app_versions.json.
    
    Returns:
        dict: Version configuration for all platforms
    """
    try:
        # Get path to data/app_versions.json
        current_dir = os.path.dirname(os.path.dirname(__file__))
        versions_file = os.path.join(current_dir, 'data', 'app_versions.json')
        
        if not os.path.exists(versions_file):
            logger.error(f"app_versions.json not found at: {versions_file}")
            return None
        
        with open(versions_file, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        logger.error(f"Failed to load app_versions.json: {e}")
        return None


@api_bp.route('/app-config', methods=['GET'])
def get_app_config():
    """
    Get app configuration including version info and update URLs.
    
    Query Parameters:
        platform (str): Platform identifier ('windows', 'ios', 'macos')
    
    Returns:
        JSON: {
            'success': bool,
            'latest_version': str,
            'min_required_version': str,
            'update_url': str,
            'release_notes': str
        }
    """
    try:
        # Get platform from query parameter
        platform = request.args.get('platform', 'windows').lower()
        
        # Validate platform
        valid_platforms = ['windows', 'ios', 'macos']
        if platform not in valid_platforms:
            return jsonify({
                'success': False,
                'error': 'invalid_platform',
                'message': f'Platform must be one of: {", ".join(valid_platforms)}'
            }), 400
        
        # Load version configuration
        versions = load_app_versions()
        
        if not versions:
            return jsonify({
                'success': False,
                'error': 'config_unavailable',
                'message': 'Version configuration unavailable'
            }), 500
        
        # Get platform-specific config
        platform_config = versions.get(platform)
        
        if not platform_config:
            return jsonify({
                'success': False,
                'error': 'platform_not_configured',
                'message': f'No configuration found for platform: {platform}'
            }), 404
        
        # Log the request (for analytics)
        logger.info(f"App config requested for platform: {platform} from IP: {request.remote_addr}")
        
        # Return configuration
        return jsonify({
            'success': True,
            'latest_version': platform_config.get('latest_version'),
            'min_required_version': platform_config.get('min_required_version'),
            'update_url': platform_config.get('update_url'),
            'release_notes': platform_config.get('release_notes', '')
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_app_config: {e}")
        return jsonify({
            'success': False,
            'error': 'internal_error',
            'message': 'An error occurred while fetching app configuration'
        }), 500
