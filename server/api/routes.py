from flask import jsonify, request
from functools import wraps
from . import api_bp
from services.trial_manager import TrialManager
from services.license_manager import LicenseManager
from services.email_service import EmailService
from services.rate_limiter import rate_limiter
from services.validation import validate_email, validate_license_key, validate_hardware_id, sanitize_string
from services.store_validation import validate_receipt, StoreValidationError
from auth.jwt_auth import create_jwt_token, require_jwt, get_current_user_id, is_premium_user
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

trial_manager = TrialManager()
license_manager = LicenseManager()
email_service = EmailService()


def require_admin_key(f):
    """
    Decorator to require admin API key for protected endpoints.
    
    Checks X-Admin-Key header against ADMIN_API_KEY from environment.
    Returns 401 Unauthorized if key is missing or invalid.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_key = Config.ADMIN_API_KEY
        provided_key = request.headers.get('X-Admin-Key')
        
        if not admin_key:
            logger.warning("ADMIN_API_KEY not configured - admin endpoint disabled")
            return jsonify({'success': False, 'error': 'admin_not_configured'}), 503
        
        if not provided_key:
            logger.warning(f"Admin endpoint access without key from IP: {request.remote_addr}")
            return jsonify({'success': False, 'error': 'unauthorized', 'message': 'Admin key required'}), 401
        
        # Use constant-time comparison to prevent timing attacks
        import hmac
        if not hmac.compare_digest(provided_key, admin_key):
            logger.warning(f"Invalid admin key attempt from IP: {request.remote_addr}")
            return jsonify({'success': False, 'error': 'unauthorized', 'message': 'Invalid admin key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function


@api_bp.route('/status', methods=['GET'])
def status():
    return jsonify({'status': 'ok'}), 200

@api_bp.route('/trial/check', methods=['GET'])
def check_trial():
    count = trial_manager.get_trial_count()
    return jsonify({'trial_count': count}), 200

@api_bp.route('/trial/increment', methods=['POST'])
def increment_trial():
    trial_manager.increment_trial()
    count = trial_manager.get_trial_count()
    return jsonify({'trial_count': count}), 200

@api_bp.route('/trial/reset', methods=['POST'])
def reset_trial():
    trial_manager.reset_trial()
    return jsonify({'trial_count': 0}), 200

@api_bp.route('/licenses/validate', methods=['POST'])
def validate_license():
    data = request.get_json()
    email = data.get('email')
    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')
    device_name = data.get('device_name', '')
    is_offline = data.get('is_offline', False)
    
    if not validate_email(email) or not validate_license_key(license_key) or not validate_hardware_id(hardware_id):
        return jsonify({'success': False, 'error': 'invalid_input'}), 400
    
    result = license_manager.validate_license(email, license_key, hardware_id, device_name, is_offline)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

@api_bp.route('/licenses/transfer', methods=['POST'])
def transfer_license():
    data = request.get_json()
    email = data.get('email')
    license_key = data.get('license_key')
    new_hardware_id = data.get('new_hardware_id')
    new_device_name = data.get('new_device_name', '')
    
    if not validate_email(email) or not validate_license_key(license_key) or not validate_hardware_id(new_hardware_id):
        return jsonify({'success': False, 'error': 'invalid_input'}), 400
    
    result = license_manager.transfer_license(email, license_key, new_hardware_id, new_device_name)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

@api_bp.route('/licenses/create', methods=['POST'])
@require_admin_key
def create_license():
    # Create a new license - ADMIN ONLY endpoint
    data = request.get_json()
    email = data.get('email')
    expires_days = data.get('expires_days', 30)
    
    if not validate_email(email):
        return jsonify({'success': False, 'error': 'invalid_email'}), 400
    
    license_key = license_manager.create_license(email, expires_days)
    
    # Send email
    try:
        email_service.send_license_email(email, license_key, expires_days)
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
    
    return jsonify({'success': True, 'license_key': license_key}), 201

@api_bp.route('/licenses/forgot', methods=['POST'])
def forgot_license():
    # Find and return a license key for a user who forgot it
    data = request.get_json()
    email = data.get('email')
    
    if not validate_email(email):
        return jsonify({'success': False, 'error': 'invalid_email'}), 400
    
    licenses = license_manager.load_licenses()
    user_licenses = [key for key, lic in licenses.items() if lic.get('email') == email and lic.get('is_active', True)]
    
    if not user_licenses:
        return jsonify({'success': False, 'error': 'no_license_found'}), 404
    
    # Send email with license keys
    try:
        email_service.send_forgot_license_email(email, user_licenses)
        return jsonify({'success': True, 'message': 'License keys sent to email'}), 200
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return jsonify({'success': False, 'error': 'email_failed'}), 500

@api_bp.route('/trial/create', methods=['POST'])
def create_trial():
    # Create a trial license for a user
    data = request.get_json()
    email = data.get('email')
    hardware_id = data.get('hardware_id')
    device_name = data.get('device_name', '')
    
    if not validate_email(email) or not validate_hardware_id(hardware_id):
        return jsonify({'success': False, 'error': 'invalid_input'}), 400
    
    result = license_manager.create_trial_license(email, hardware_id, device_name)
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400

@api_bp.route('/trial/check-eligibility', methods=['POST'])
def check_trial_eligibility():
    # Check if a user is eligible for a trial
    data = request.get_json()
    email = data.get('email')
    hardware_id = data.get('hardware_id')
    
    if not validate_email(email) or not validate_hardware_id(hardware_id):
        return jsonify({'success': False, 'error': 'invalid_input'}), 400
    
    result = license_manager.check_trial_eligibility(email, hardware_id)
    return jsonify(result), 200


@api_bp.route('/trial/status/<license_key>', methods=['GET'])
def trial_status(license_key):
    # Get trial status for a license key
    if not validate_license_key(license_key):
        return jsonify({'success': False, 'error': 'invalid_license_key'}), 400
    
    is_trial = license_manager.is_trial_license(license_key)
    
    if not is_trial:
        return jsonify({'success': False, 'error': 'not_a_trial'}), 400
    
    trials = license_manager.load_trials()
    trial_data = trials.get(license_key)
    
    if not trial_data:
        return jsonify({'success': False, 'error': 'trial_not_found'}), 404
    
    return jsonify({'success': True, **trial_data}), 200


# ============================================================================
# ADMIN ENDPOINTS - PLATFORM MIGRATION
# ============================================================================

@api_bp.route('/admin/migrate-platforms', methods=['POST'])
@require_admin_key
def admin_migrate_platforms():
    """
    Migrate existing licenses to include platform field.
    
    This is a one-time operation to update licenses created before
    multi-platform support was added. Safe to run multiple times.
    
    ADMIN ONLY - Requires X-Admin-Key header
    """
    try:
        result = license_manager.migrate_to_platform_schema()
        return jsonify({
            'success': True,
            'migration_result': result,
            'message': f"Migrated {result['migrated']} licenses, {result['already_migrated']} already had platform, {result['errors']} errors"
        }), 200
    except Exception as e:
        logger.error(f"Platform migration failed: {e}")
        return jsonify({
            'success': False,
            'error': 'migration_failed',
            'message': str(e)
        }), 500


@api_bp.route('/admin/platform-stats', methods=['GET'])
@require_admin_key
def admin_platform_stats():
    """
    Get statistics about licenses by platform.
    
    ADMIN ONLY - Requires X-Admin-Key header
    """
    try:
        licenses = license_manager.load_licenses()
        
        stats = {
            'total': len(licenses),
            'by_platform': {},
            'no_platform': 0
        }
        
        for license_data in licenses.values():
            platform = license_data.get('platform')
            if platform:
                stats['by_platform'][platform] = stats['by_platform'].get(platform, 0) + 1
            else:
                stats['no_platform'] += 1
        
        from services.license_manager import Platform
        return jsonify({
            'success': True,
            'stats': stats,
            'platforms_available': Platform.all_values()
        }), 200
        
    except Exception as e:
        logger.error(f"Platform stats failed: {e}")
        return jsonify({
            'success': False,
            'error': 'stats_failed',
            'message': str(e)
        }), 500


@api_bp.route('/admin/find-by-platform', methods=['GET'])
@require_admin_key
def admin_find_by_platform():
    """
    Find all licenses from a specific platform.
    
    Query params:
        platform: Platform name ('gumroad', 'msstore', etc.)
    
    ADMIN ONLY - Requires X-Admin-Key header
    """
    try:
        platform = request.args.get('platform')
        
        if not platform:
            return jsonify({
                'success': False,
                'error': 'missing_platform',
                'message': 'Platform query parameter required'
            }), 400
        
        from services.license_manager import Platform
        if not Platform.is_valid(platform):
            return jsonify({
                'success': False,
                'error': 'invalid_platform',
                'message': f'Platform must be one of: {Platform.all_values()}'
            }), 400
        
        licenses = license_manager.load_licenses()
        filtered = {
            key: data for key, data in licenses.items()
            if data.get('platform') == platform
        }
        
        # Sanitize sensitive data
        sanitized = {}
        for key, data in filtered.items():
            sanitized[key] = {
                'email': data.get('email'),
                'platform': data.get('platform'),
                'is_active': data.get('is_active'),
                'created_date': data.get('created_date'),
                'expiry_date': data.get('expiry_date'),
            }
        
        return jsonify({
            'success': True,
            'platform': platform,
            'count': len(sanitized),
            'licenses': sanitized
        }), 200
        
    except Exception as e:
        logger.error(f"Find by platform failed: {e}")
        return jsonify({
            'success': False,
            'error': 'lookup_failed',
            'message': str(e)
        }), 500


# ============================================================================
# STORE VALIDATION ENDPOINTS
# ============================================================================

@api_bp.route('/store/validate-receipt', methods=['POST'])
def validate_store_receipt():
    """
    Validate a store receipt and issue JWT token.
    
    Platform-agnostic endpoint for MS Store and Apple App Store.
    
    Request:
        {
            "receipt_data": "<base64 encoded receipt>",
            "platform": "msstore" | "appstore",
            "product_id": "imgapp_lifetime" | "imgapp_energy_100"
        }
    
    Response:
        {
            "success": true,
            "is_premium": true,
            "energy_balance": 50,
            "jwt_token": "eyJ..."
        }
    """
    try:
        data = request.get_json()
        receipt_data = data.get('receipt_data')
        platform = data.get('platform')
        product_id = data.get('product_id')
        
        if not all([receipt_data, platform, product_id]):
            return jsonify({
                'success': False,
                'error': 'missing_fields',
                'message': 'receipt_data, platform, and product_id required'
            }), 400
        
        # Validate receipt with appropriate store API
        validation_result = validate_receipt(receipt_data, platform, product_id)
        
        if not validation_result.get('valid'):
            return jsonify({
                'success': False,
                'error': 'invalid_receipt',
                'message': 'Receipt validation failed'
            }), 400
        
        # Extract store user ID from receipt (platform-specific)
        # For MS Store: extract from receipt XML
        # For App Store: extract from receipt JSON
        store_user_id = _extract_user_id_from_receipt(receipt_data, platform)
        
        # Determine if premium based on product type
        is_premium = validation_result['product_type'] == 'lifetime'
        energy_to_add = validation_result.get('energy_amount', 0)
        
        # Get or create user profile
        user_profile = license_manager.get_or_create_user_profile(store_user_id, platform)
        
        # Update user profile
        if is_premium:
            user_profile['is_premium'] = True
        if energy_to_add > 0:
            user_profile['energy_balance'] = user_profile.get('energy_balance', 0) + energy_to_add
        
        license_manager.save_user_profile(store_user_id, user_profile)
        
        # Create JWT token
        jwt_token = create_jwt_token(store_user_id, platform, is_premium)
        
        logger.info(f"Receipt validated for user {store_user_id[:8]}... (platform: {platform}, premium: {is_premium})")
        
        return jsonify({
            'success': True,
            'is_premium': is_premium,
            'energy_balance': user_profile.get('energy_balance', Config.DAILY_FREE_ENERGY),
            'jwt_token': jwt_token
        }), 200
        
    except StoreValidationError as e:
        logger.warning(f"Receipt validation error: {e}")
        return jsonify({
            'success': False,
            'error': 'validation_error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Receipt validation failed: {e}")
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': 'Internal server error'
        }), 500


# ============================================================================
# ENERGY ENDPOINTS (JWT Protected)
# ============================================================================

@api_bp.route('/energy/sync', methods=['POST'])
@require_jwt
def energy_sync():
    """
    Sync current energy balance from server.
    
    JWT Protected - Requires Bearer token in Authorization header.
    
    Response:
        {
            "success": true,
            "balance": 45,
            "max_daily": 50,
            "is_premium": false,
            "signature": "..."
        }
    """
    try:
        user_id = get_current_user_id()
        is_premium = is_premium_user()
        
        # Get user profile
        user_profile = license_manager.get_user_profile(user_id)
        
        if not user_profile:
            return jsonify({
                'success': False,
                'error': 'user_not_found'
            }), 404
        
        # Check if daily reset is needed
        license_manager.check_daily_energy_reset(user_id, user_profile)
        
        # Generate signature for client verification
        import hmac
        import hashlib
        from datetime import datetime
        
        timestamp = datetime.utcnow().isoformat()
        balance = user_profile.get('energy_balance', Config.DAILY_FREE_ENERGY)
        payload = f"{balance}:{timestamp}"
        signature = hmac.new(
            Config.SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return jsonify({
            'success': True,
            'balance': balance,
            'max_daily': Config.DAILY_FREE_ENERGY,
            'is_premium': user_profile.get('is_premium', False),
            'timestamp': timestamp,
            'signature': signature
        }), 200
        
    except Exception as e:
        logger.error(f"Energy sync failed: {e}")
        return jsonify({
            'success': False,
            'error': 'sync_failed',
            'message': str(e)
        }), 500


@api_bp.route('/energy/reserve', methods=['POST'])
@require_jwt
def energy_reserve():
    """
    Reserve energy for a high-cost job (synchronous validation).
    
    JWT Protected - Requires Bearer token.
    
    Request:
        {
            "amount": 10
        }
    
    Response:
        {
            "success": true,
            "approved": true,
            "new_balance": 40,
            "signature": "..."
        }
    """
    try:
        user_id = get_current_user_id()
        is_premium = is_premium_user()
        
        # Premium users bypass energy checks
        if is_premium:
            return jsonify({
                'success': True,
                'approved': True,
                'new_balance': 999,  # Unlimited for premium
                'is_premium': True
            }), 200
        
        data = request.get_json()
        amount = data.get('amount', 0)
        
        if amount <= 0:
            return jsonify({
                'success': False,
                'error': 'invalid_amount'
            }), 400
        
        # Get user profile
        user_profile = license_manager.get_user_profile(user_id)
        
        if not user_profile:
            return jsonify({
                'success': False,
                'error': 'user_not_found'
            }), 404
        
        # Check balance
        current_balance = user_profile.get('energy_balance', 0)
        
        if current_balance < amount:
            return jsonify({
                'success': True,
                'approved': False,
                'error': 'insufficient_energy',
                'current_balance': current_balance,
                'required': amount
            }), 402  # Payment Required
        
        # Deduct energy
        new_balance = current_balance - amount
        user_profile['energy_balance'] = new_balance
        license_manager.save_user_profile(user_id, user_profile)
        
        # Generate signature
        import hmac
        import hashlib
        from datetime import datetime
        
        timestamp = datetime.utcnow().isoformat()
        payload = f"{new_balance}:{timestamp}"
        signature = hmac.new(
            Config.SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        logger.info(f"Energy reserved: {amount} for user {user_id[:8]}... (new balance: {new_balance})")
        
        return jsonify({
            'success': True,
            'approved': True,
            'new_balance': new_balance,
            'timestamp': timestamp,
            'signature': signature
        }), 200
        
    except Exception as e:
        logger.error(f"Energy reserve failed: {e}")
        return jsonify({
            'success': False,
            'error': 'reserve_failed',
            'message': str(e)
        }), 500


@api_bp.route('/energy/report', methods=['POST'])
@require_jwt
def energy_report():
    """
    Report accumulated local usage (batch sync).
    
    JWT Protected - Requires Bearer token.
    
    Request:
        {
            "usage": 5,
            "last_signature": "..."
        }
    
    Response:
        {
            "success": true,
            "new_balance": 45,
            "signature": "..."
        }
    """
    try:
        user_id = get_current_user_id()
        is_premium = is_premium_user()
        
        # Premium users don't need to report usage
        if is_premium:
            return jsonify({
                'success': True,
                'is_premium': True
            }), 200
        
        data = request.get_json()
        usage = data.get('usage', 0)
        
        if usage <= 0:
            return jsonify({
                'success': False,
                'error': 'invalid_usage'
            }), 400
        
        # Get user profile
        user_profile = license_manager.get_user_profile(user_id)
        
        if not user_profile:
            return jsonify({
                'success': False,
                'error': 'user_not_found'
            }), 404
        
        # Deduct usage from balance
        current_balance = user_profile.get('energy_balance', 0)
        new_balance = max(0, current_balance - usage)
        user_profile['energy_balance'] = new_balance
        license_manager.save_user_profile(user_id, user_profile)
        
        # Generate signature
        import hmac
        import hashlib
        from datetime import datetime
        
        timestamp = datetime.utcnow().isoformat()
        payload = f"{new_balance}:{timestamp}"
        signature = hmac.new(
            Config.SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        logger.info(f"Energy usage reported: {usage} for user {user_id[:8]}... (new balance: {new_balance})")
        
        return jsonify({
            'success': True,
            'new_balance': new_balance,
            'timestamp': timestamp,
            'signature': signature
        }), 200
        
    except Exception as e:
        logger.error(f"Energy report failed: {e}")
        return jsonify({
            'success': False,
            'error': 'report_failed',
            'message': str(e)
        }), 500


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _extract_user_id_from_receipt(receipt_data: str, platform: str) -> str:
    """
    Extract store user ID from receipt data.
    
    For MS Store: Parse XML receipt for user ID
    For App Store: Parse JSON receipt for user ID
    
    Args:
        receipt_data: Receipt blob
        platform: "msstore" or "appstore"
        
    Returns:
        str: Store user ID
    """
    import base64
    import xml.etree.ElementTree as ET
    
    if platform == "msstore":
        try:
            # MS Store receipts are XML
            receipt_xml = base64.b64decode(receipt_data).decode('utf-8')
            root = ET.fromstring(receipt_xml)
            # Extract user ID from receipt (adjust XPath as needed)
            user_id = root.find('.//UserId').text if root.find('.//UserId') is not None else 'unknown'
            return user_id
        except Exception as e:
            logger.warning(f"Failed to extract MS Store user ID: {e}")
            return f"msstore_{hash(receipt_data) % 1000000}"
    
    elif platform == "appstore":
        try:
            # App Store receipts are JSON
            import json
            receipt_json = base64.b64decode(receipt_data).decode('utf-8')
            receipt = json.loads(receipt_json)
            user_id = receipt.get('user_id', 'unknown')
            return user_id
        except Exception as e:
            logger.warning(f"Failed to extract App Store user ID: {e}")
            return f"appstore_{hash(receipt_data) % 1000000}"
    
    return "unknown"