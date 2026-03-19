"""
Update API Endpoints

Provides endpoints for checking and downloading updates.
Requires valid license for access.
"""
from flask import jsonify, request, Response
from functools import wraps
import logging
from . import api_bp
from services.update_manifest import UpdateManifestService
from auth.jwt_auth import require_jwt, get_current_user_id

logger = logging.getLogger(__name__)

update_service = UpdateManifestService()


@api_bp.route('/updates/manifest', methods=['GET'])
@require_jwt
def get_update_manifest():
    """
    Get manifest of available updates.

    JWT Protected — requires Bearer token from register-free or validate-receipt.

    Returns:
        JSON: {
            'presets': [{'id', 'version', 'hash', 'path'}]
        }
    """
    try:
        manifest = update_service.generate_manifest()

        user_id = get_current_user_id()
        logger.info(f"Manifest requested by user {user_id[:8]}...")

        return jsonify({
            'success': True,
            'manifest': manifest
        }), 200

    except Exception as e:
        logger.error(f"Failed to generate manifest: {e}")
        return jsonify({
            'success': False,
            'error': 'manifest_generation_failed',
            'message': str(e)
        }), 500


@api_bp.route('/updates/download/preset/<preset_id>', methods=['GET'])
@require_jwt
def download_preset(preset_id):
    """
    Download preset YAML content.
    
    Args:
        preset_id: Preset filename without extension
        
    Returns:
        YAML content as text/plain
    """
    try:
        # Sanitize preset_id to prevent directory traversal
        if '..' in preset_id or '/' in preset_id or '\\' in preset_id:
            return jsonify({
                'success': False,
                'error': 'invalid_preset_id',
                'message': 'Invalid preset ID'
            }), 400
        
        content = update_service.get_preset_content(preset_id)
        
        if content is None:
            return jsonify({
                'success': False,
                'error': 'preset_not_found',
                'message': f'Preset {preset_id} not found'
            }), 404
        
        logger.info(f"Preset {preset_id} downloaded by user {get_current_user_id()[:8]}...")
        
        return Response(
            content,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename="{preset_id}.yaml"'}
        )
        
    except Exception as e:
        logger.error(f"Failed to download preset {preset_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'download_failed',
            'message': str(e)
        }), 500

