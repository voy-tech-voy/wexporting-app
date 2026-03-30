from flask import jsonify, request
from functools import wraps
from . import api_bp
from services.license_manager import LicenseManager
from services.email_service import EmailService
from services.rate_limiter import rate_limiter
from services.validation import validate_email
from services.store_validation import validate_receipt, StoreValidationError
from auth.jwt_auth import create_jwt_token, require_jwt, get_current_user_id, is_premium_user
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

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
        result = license_manager.migrate_existing_licenses_platform()
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
            "energy_balance": 35,
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
        # For dev mocks the client sends its per-run user ID explicitly; use it
        # so each run gets a fresh profile instead of hitting the stale shared one.
        if data.get('is_dev_mock') and data.get('store_user_id'):
            store_user_id = data['store_user_id']
        else:
            store_user_id = _extract_user_id_from_receipt(receipt_data, platform)
        
        # Determine if premium based on product type
        # Use new helper to correctly map product_id to type
        product_type = _get_product_type_from_id(product_id)
        is_lifetime = product_type == 'lifetime'
        is_day_pass = product_type == 'day_pass'
        
        # Use new helper to correctly get energy amount
        energy_to_add = _get_energy_amount_from_id(product_id)
        
        # Get or create user profile
        user_profile = license_manager.get_or_create_user_profile(store_user_id, platform)
        
        # Update user profile
        if is_lifetime:
            user_profile['is_premium'] = True
            
        if is_day_pass:
            # Set expiry to 24 hours from now
            from datetime import datetime, timedelta
            expiry = datetime.utcnow() + timedelta(days=1)
            # If already has expiry, extend it? No, simpler to just set from now for Day Pass.
            # Or strict 24h from purchase?
            user_profile['premium_expiry'] = expiry.isoformat()
            
        if energy_to_add > 0:
            if product_id in _PRODUCT_LIMIT_PACKS:
                # Durable limit pack: permanently increases daily max AND
                # tops up the current balance immediately so the benefit kicks in today.
                user_profile['purchased_energy'] = user_profile.get('purchased_energy', 0) + energy_to_add
                user_profile['energy_balance'] = user_profile.get('energy_balance', 0) + energy_to_add
                logger.info(f"Limit pack: purchased_energy += {energy_to_add} (new max: {35 + user_profile['purchased_energy']}), energy_balance += {energy_to_add}")
            else:
                # Consumable pack: one-time balance addition.
                # Max daily stays unchanged; only the available balance increases.
                user_profile['energy_balance'] = user_profile.get('energy_balance', 0) + energy_to_add
                logger.info(f"Consumable pack: energy_balance += {energy_to_add}")
        
        license_manager.save_user_profile(store_user_id, user_profile)
        
        # Determine actual premium status for JWT
        # Premium if: Lifetime OR (Expiry exists AND Expiry > Now)
        effective_is_premium = user_profile.get('is_premium', False)
        
        if not effective_is_premium:
            expiry_str = user_profile.get('premium_expiry')
            if expiry_str:
                from datetime import datetime
                if datetime.fromisoformat(expiry_str) > datetime.utcnow():
                    effective_is_premium = True
        
        # Create JWT token
        jwt_token = create_jwt_token(store_user_id, platform, effective_is_premium)
        
        logger.info(f"Receipt validated for user {store_user_id[:8]}... (platform: {platform}, premium: {effective_is_premium})")
        
        return jsonify({
            'success': True,
            'is_premium': effective_is_premium,
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


@api_bp.route('/store/acknowledge-purchase', methods=['POST'])
@require_jwt
def acknowledge_purchase():
    """
    JWT-authenticated purchase acknowledgement.
    Called after a successful MS Store purchase UI.
    No receipt needed — JWT proves identity, Store UI proved payment.
    """
    data = request.get_json() or {}
    product_id = data.get('product_id', '').strip()
    if not product_id:
        return jsonify({"success": False, "error": "missing_product_id"}), 400

    store_user_id = get_current_user_id()
    platform = request.jwt_claims.get('platform', 'msstore')

    product_type = _get_product_type_from_id(product_id)
    energy_to_add = _get_energy_amount_from_id(product_id)

    profile = license_manager.get_or_create_user_profile(store_user_id, platform)
    license_manager.check_daily_energy_reset(store_user_id, profile)
    profile = license_manager.get_user_profile(store_user_id)

    is_premium = profile.get('is_premium', False)

    if product_type == 'lifetime':
        license_manager.update_user_profile(store_user_id, {'is_premium': True})
        is_premium = True
    elif product_type == 'limit_pack' and energy_to_add > 0:
        new_purchased = profile.get('purchased_energy', 0) + energy_to_add
        new_balance = profile.get('energy_balance', 0) + energy_to_add
        license_manager.update_user_profile(store_user_id, {
            'purchased_energy': new_purchased,
            'energy_balance': new_balance,
        })
    elif energy_to_add > 0:
        new_balance = profile.get('energy_balance', 0) + energy_to_add
        license_manager.update_user_profile(store_user_id, {'energy_balance': new_balance})

    profile = license_manager.get_user_profile(store_user_id)
    jwt_token = create_jwt_token(store_user_id, platform, is_premium)

    logger.info(f"Purchase acknowledged: user={store_user_id[:8]}... product={product_id} "
                f"type={product_type} energy_added={energy_to_add} premium={is_premium}")

    return jsonify({
        "success": True,
        "is_premium": is_premium,
        "energy_balance": profile.get('energy_balance', 0),
        "jwt_token": jwt_token,
    }), 200


@api_bp.route('/store/register-free', methods=['POST'])
def register_free_tier():
    """
    Register a free-tier user and issue a JWT token.

    No purchase required. Called on first launch for users who have never made
    a purchase. Creates a server profile (idempotent) and returns a JWT so the
    server — not local files — controls the energy balance.

    Request:
        {
            "store_user_id": "<ms store / apple user id>",
            "platform": "msstore" | "appstore"
        }

    Response:
        {
            "success": true,
            "is_premium": false,
            "energy_balance": 35,
            "jwt_token": "eyJ..."
        }
    """
    try:
        data = request.get_json()
        store_user_id = (data.get('store_user_id') or '').strip()
        platform = (data.get('platform') or '').strip()

        if not store_user_id or not platform:
            return jsonify({
                'success': False,
                'error': 'missing_fields',
                'message': 'store_user_id and platform required'
            }), 400

        # Reject known fake/dev identifiers
        _REJECTED_IDS = {'dev-user', 'unknown', 'test', 'null', 'none'}
        if store_user_id.lower() in _REJECTED_IDS:
            return jsonify({
                'success': False,
                'error': 'invalid_store_id',
                'message': 'A valid store user ID is required'
            }), 400

        # Rate-limit by IP to prevent abuse
        rate_check = rate_limiter.check_rate_limit(
            'login_validate',
            ip_address=request.remote_addr
        )
        if not rate_check.get('allowed', True):
            return jsonify({
                'success': False,
                'error': 'rate_limited',
                'message': rate_check.get('message', 'Too many requests'),
                'retry_after': rate_check.get('retry_after', 600)
            }), 429

        # Get or create user profile (idempotent — safe to call every launch)
        user_profile = license_manager.get_or_create_user_profile(store_user_id, platform)

        # Refresh daily energy if a new UTC day has started
        license_manager.check_daily_energy_reset(store_user_id, user_profile)

        # Determine effective premium status
        is_premium = user_profile.get('is_premium', False)
        if not is_premium:
            expiry_str = user_profile.get('premium_expiry')
            if expiry_str:
                from datetime import datetime
                if datetime.fromisoformat(expiry_str) > datetime.utcnow():
                    is_premium = True

        # Issue JWT token
        jwt_token = create_jwt_token(store_user_id, platform, is_premium)

        logger.info(f"Free-tier registered: user {store_user_id[:8]}... (platform: {platform})")

        return jsonify({
            'success': True,
            'is_premium': is_premium,
            'energy_balance': user_profile.get('energy_balance', Config.DAILY_FREE_ENERGY),
            'jwt_token': jwt_token
        }), 200

    except Exception as e:
        logger.error(f"register-free failed: {e}")
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
            "max_daily": 35,
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
        
        # max_daily = free allowance + any permanently purchased energy expansion
        purchased_energy = user_profile.get('purchased_energy', 0)
        max_daily = Config.DAILY_FREE_ENERGY + purchased_energy
        
        return jsonify({
            'success': True,
            'balance': balance,
            'max_daily': max_daily,
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
        
        # Deduct energy (Dual Pool Logic)
        new_balance = current_balance - amount
        user_profile['energy_balance'] = new_balance
        
        # If we dipped below purchased amount, clamp purchased pool
        # Example: Total 75 (35 Free + 40 Paid). Spend 60. New Total 15.
        # Paid was 40. Now must be 15. (Used 35 Free + 25 Paid)
        current_purchased = user_profile.get('purchased_energy', 0)
        if new_balance < current_purchased:
             user_profile['purchased_energy'] = new_balance
             
        # Save profile
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

        # Clamp purchased_energy if balance dipped below it (same logic as /energy/reserve)
        current_purchased = user_profile.get('purchased_energy', 0)
        if new_balance < current_purchased:
            user_profile['purchased_energy'] = new_balance

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

# ============================================================================
# PRODUCT ID LOOKUP TABLES
# Maps MS Store product IDs (from purchase_options.json) to their types and amounts
# ============================================================================
_PRODUCT_TYPE_MAP = {
    # MS Store product IDs
    '9PFHR7GMBT0T': 'energy_pack',   # 500 Credits (consumable)
    '9NNK6Q3WZN2M': 'limit_pack',    # Daily Focus Pack (+200 permanent max)
    '9P4WCMTCH89V': 'lifetime',      # Premium Lifetime
    # Generic keyword-based fallbacks (for future products)
}

# Products that increase the daily LIMIT permanently (durable).
# All other energy_pack products are consumable one-time balance additions.
_PRODUCT_LIMIT_PACKS = {'9NNK6Q3WZN2M'}

_PRODUCT_ENERGY_MAP = {
    '9PFHR7GMBT0T': 500,   # 500 Credits
    '9NNK6Q3WZN2M': 200,   # Daily Focus Pack (+200 max)
    '9P4WCMTCH89V': 0,     # Premium Lifetime - no energy, grants unlimited
}


def _get_product_type_from_id(product_id: str) -> str:
    """
    Determine product type from product ID.
    
    First checks explicit MS Store ID lookup table, then falls back to
    keyword matching for forward-compatibility with future products.
    
    Args:
        product_id: Product identifier
        
    Returns:
        str: "lifetime", "energy_pack", or "day_pass"
    """
    # Check explicit lookup table first (MS Store IDs)
    if product_id in _PRODUCT_TYPE_MAP:
        return _PRODUCT_TYPE_MAP[product_id]
    
    # Keyword-based fallback for future products
    pid_lower = product_id.lower()
    if 'lifetime' in pid_lower or 'premium' in pid_lower:
        return 'lifetime'
    elif 'day_pass' in pid_lower:
        return 'day_pass'
    elif 'energy' in pid_lower or 'credit' in pid_lower:
        return 'energy_pack'
    else:
        logger.warning(f"Unknown product_id '{product_id}', defaulting to 'lifetime'")
        return 'lifetime'


def _get_energy_amount_from_id(product_id: str) -> int:
    """
    Extract energy amount from product ID.
    
    First checks explicit MS Store ID lookup table (e.g. 9NBLGGH42DRH -> 500),
    then falls back to regex for forward-compatible future products
    that encode the amount in their ID string (e.g. 'imgapp_energy_100').
    
    Args:
        product_id: Product identifier
        
    Returns:
        int: Energy amount, or 0 if not found
    """
    # Check explicit lookup table first
    if product_id in _PRODUCT_ENERGY_MAP:
        return _PRODUCT_ENERGY_MAP[product_id]
    
    # Regex-based fallback for future products with amount in ID
    import re
    match = re.search(r'(?:energy|credit)[_-](\d+)', product_id.lower())
    if match:
        return int(match.group(1))
    return 0

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
    import hashlib
    import xml.etree.ElementTree as ET

    if platform == "msstore":
        # DEV MOCK: return a stable user ID so all mock purchases hit the same profile
        if receipt_data and receipt_data.startswith("DEV_MOCK_TX_"):
            return "msstore_DEV_MOCK_USER_001"
        try:
            receipt_xml = base64.b64decode(receipt_data).decode('utf-8')
            root = ET.fromstring(receipt_xml)
            user_id_el = root.find('.//UserId')
            if user_id_el is not None and user_id_el.text:
                return user_id_el.text
        except Exception as e:
            logger.warning(f"Failed to extract MS Store user ID: {e}")
        # Deterministic fallback (stable across server restarts)
        return f"msstore_{hashlib.sha256(receipt_data.encode()).hexdigest()[:12]}"

    elif platform == "appstore":
        try:
            import json as _json
            receipt_json = base64.b64decode(receipt_data).decode('utf-8')
            receipt = _json.loads(receipt_json)
            user_id = receipt.get('user_id', '')
            if user_id:
                return user_id
        except Exception as e:
            logger.warning(f"Failed to extract App Store user ID: {e}")
        return f"appstore_{hashlib.sha256(receipt_data.encode()).hexdigest()[:12]}"

    return "unknown"