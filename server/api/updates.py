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
from services.license_manager import LicenseManager

logger = logging.getLogger(__name__)

update_service = UpdateManifestService()
license_manager = LicenseManager()


def require_valid_license(f):
    """
    Decorator to require valid license for update endpoints.
    
    Checks Authorization header for Bearer token (license key).
    Validates license is active and not expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning(f"Update request without auth from IP: {request.remote_addr}")
            return jsonify({
                'success': False,
                'error': 'unauthorized',
                'message': 'Valid license required for updates'
            }), 401
        
        license_key = auth_header.replace('Bearer ', '').strip()
        
        # Quick validation - just check if license exists and is active
        licenses = license_manager.load_licenses()
        trials = license_manager.load_trials()
        
        license_data = licenses.get(license_key) or trials.get(license_key)
        
        if not license_data:
            logger.warning(f"Update request with invalid license from IP: {request.remote_addr}")
            return jsonify({
                'success': False,
                'error': 'invalid_license',
                'message': 'License not found'
            }), 401
        
        if not license_data.get('is_active', False):
            return jsonify({
                'success': False,
                'error': 'license_inactive',
                'message': 'License is not active'
            }), 401
        
        # Check expiry
        from datetime import datetime
        try:
            expiry_date = datetime.fromisoformat(license_data['expiry_date'])
            if datetime.now() > expiry_date:
                return jsonify({
                    'success': False,
                    'error': 'license_expired',
                    'message': 'License has expired'
                }), 401
        except:
            pass
        
        # Store license info in request context for logging
        request.license_key = license_key
        request.license_email = license_data.get('email')
        
        return f(*args, **kwargs)
    
    return decorated_function


@api_bp.route('/updates/manifest', methods=['GET'])
@require_valid_license
def get_update_manifest():
    """
    Get manifest of available updates.
    
    Returns:
        JSON: {
            'presets': [{'id', 'version', 'hash', 'path'}],
            'estimators': [{'id', 'version', 'hash', 'type'}]
        }
    """
    try:
        manifest = update_service.generate_manifest()
        
        logger.info(f"Manifest requested by {request.license_email}")
        
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
@require_valid_license
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
        
        logger.info(f"Preset {preset_id} downloaded by {request.license_email}")
        
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


@api_bp.route('/updates/download/estimator/<estimator_id>', methods=['GET'])
@require_valid_license
def download_estimator(estimator_id):
    """
    Download estimator Python content.
    
    Args:
        estimator_id: Estimator filename without extension
        
    Returns:
        Python content as text/plain
    """
    try:
        # Sanitize estimator_id to prevent directory traversal
        if '..' in estimator_id or '/' in estimator_id or '\\' in estimator_id:
            return jsonify({
                'success': False,
                'error': 'invalid_estimator_id',
                'message': 'Invalid estimator ID'
            }), 400
        
        content = update_service.get_estimator_content(estimator_id)
        
        if content is None:
            return jsonify({
                'success': False,
                'error': 'estimator_not_found',
                'message': f'Estimator {estimator_id} not found'
            }), 404
        
        logger.info(f"Estimator {estimator_id} downloaded by {request.license_email}")
        
        return Response(
            content,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename="{estimator_id}.py"'}
        )
        
    except Exception as e:
        logger.error(f"Failed to download estimator {estimator_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'download_failed',
            'message': str(e)
        }), 500
