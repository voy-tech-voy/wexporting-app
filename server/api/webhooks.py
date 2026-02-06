from flask import jsonify, request
from . import webhook_bp
from services.license_manager import LicenseManager, Platform, get_platform_sale_id_field
from services.email_service import EmailService
from services.backup_manager import BackupManager
from config.settings import Config
import logging
import json
import hmac
import hashlib
from datetime import datetime
import os
import base64
import requests
from functools import wraps

logger = logging.getLogger(__name__)
license_manager = LicenseManager()
email_service = EmailService()
backup_manager = BackupManager()

# Webhook debug log file
WEBHOOK_DEBUG_LOG = 'webhook_debug.jsonl'


# ============================================================================
# GUMROAD WEBHOOK HANDLERS
# ============================================================================

def verify_gumroad_seller(data):
    """
    Verify Gumroad webhook by checking seller_id.
    
    NOTE: Gumroad does NOT provide HMAC webhook signatures like Stripe.
    We verify authenticity by checking seller_id matches our account.
    
    Args:
        data: Webhook POST data dictionary
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    expected_seller_id = Config.GUMROAD_SELLER_ID
    
    if not expected_seller_id:
        logger.warning("GUMROAD_SELLER_ID not configured - skipping seller verification")
        return True, None  # Allow in dev mode when not configured
    
    seller_id = data.get('seller_id', '')
    
    if not seller_id:
        logger.warning("No seller_id in webhook payload")
        return False, "Missing seller_id in payload"
    
    # Use constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(str(seller_id), str(expected_seller_id))
    
    if not is_valid:
        logger.warning(f"Webhook rejected: seller_id mismatch. Got '{seller_id}', expected '{expected_seller_id}'")
        return False, "Invalid seller_id"
    
    # Optional: Also verify product_id if configured
    expected_product_id = Config.GUMROAD_PRODUCT_ID
    if expected_product_id:
        product_id = data.get('product_id', '')
        if product_id and not hmac.compare_digest(str(product_id), str(expected_product_id)):
            logger.warning(f"Webhook for unexpected product: {product_id}")
            # Don't reject, just log - might be a different product
    
    return True, None

# Map Gumroad Product Permalinks/IDs to duration in days
PRODUCT_DURATIONS = {
    "imgwave": 30,  # Default to 30 days (will be overridden by variant tier)
    "free_trial_3h": 0.125,
    "daily_sub": 1,
    "monthly_sub": 30,
    "yearly_sub": 365,
    "lifetime_deal": 36500,
}

# Map Gumroad variant tiers to duration in days
TIER_DURATIONS = {
    "Pricing": 30,  # Default tier from your product (when no explicit tier)
    "Monthly": 30,
    "Yearly": 365,
    "Lifetime": 36500,  # ~100 years
    "3-Month": 90,
    "6-Month": 180,
}

def normalize_gumroad_purchase(data, duration_days, tier):
    """
    Normalize Gumroad webhook data into standardized purchase_info structure.
    This allows future payment providers (Stripe, direct sales, etc) to use the same format.
    
    Args:
        data: Raw Gumroad webhook POST data
        duration_days: Calculated license duration based on tier/product
        tier: Calculated tier (e.g., 'Lifetime', 'Monthly')
    
    Returns:
        dict: Standardized purchase_info structure
    """
    purchase_date = data.get('sale_timestamp', datetime.utcnow().isoformat())
    is_recurring = data.get('recurrence') == 'monthly' or data.get('subscription_id') is not None
    
    purchase_info = {
        'source': 'gumroad',
        'source_license_key': data.get('license_key'),
        'sale_id': data.get('sale_id'),
        'customer_id': data.get('purchaser_id'),
        'product_id': data.get('product_id'),
        'product_name': data.get('product_name', ''),
        'tier': tier,  # Use calculated tier, not raw webhook data
        'price': data.get('price'),
        'currency': data.get('currency', 'usd').lower(),
        'purchase_date': purchase_date,
        'is_recurring': is_recurring,
        'recurrence': data.get('recurrence'),
        'subscription_id': data.get('subscription_id'),
        'renewal_date': None,  # Calculate if recurring
        'is_refunded': data.get('refunded') == 'true',
        'refund_date': None,  # Not provided by Gumroad in webhook
        'is_disputed': data.get('disputed') == 'true',
        'is_test': data.get('test') == 'true'
    }
    
    return purchase_info

def save_webhook_log(data, status, response):
    """Save raw webhook data to file for debugging"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "raw_data": dict(data),
        "response": response
    }
    
    try:
        with open('webhook_logs.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
        logger.info(f"Webhook logged to webhook_logs.jsonl")
    except Exception as e:
        logger.error(f"Failed to save webhook log: {e}")

@webhook_bp.route('/gumroad', methods=['POST'])
def gumroad_webhook():
    """Handle Gumroad purchase webhooks
    
    SECURITY NOTE: Gumroad does NOT provide webhook signatures.
    We verify authenticity by checking seller_id matches our account.
    """
    
    # Try to get data from form first, then JSON
    data = request.form.to_dict() if request.form else request.get_json() or {}
    
    # LOG EVERYTHING including seller_id for debugging
    logger.info(f"=== GUMROAD WEBHOOK RAW DATA ===")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"Form data: {request.form.to_dict()}")
    logger.info(f"JSON data: {request.get_json()}")
    logger.info(f"Parsed data: {json.dumps(data, indent=2)}")
    logger.info(f"seller_id in data: {data.get('seller_id', 'NOT FOUND')}")
    logger.info(f"=== END RAW DATA ===")
    
    if not data:
        error_response = {"error": "No data received"}
        save_webhook_log({}, "error", error_response)
        return jsonify(error_response), 400
    
    # SECURITY: Verify webhook seller_id
    if Config.VERIFY_WEBHOOK_SELLER:
        is_valid, error_msg = verify_gumroad_seller(data)
        
        if not is_valid:
            error_response = {"error": error_msg or "Webhook verification failed"}
            save_webhook_log({'verification_failed': True, 'seller_id': data.get('seller_id')}, "security_error", error_response)
            logger.warning(f"Webhook seller verification failed from IP: {request.remote_addr}")
            return jsonify(error_response), 403
    
    # IDEMPOTENCY: Check if we already processed this sale_id
    sale_id = data.get('sale_id')
    if sale_id:
        existing = license_manager.find_license_by_sale_id(sale_id)
        if existing:
            logger.info(f"Duplicate webhook for sale_id {sale_id} - already processed")
            return jsonify({"status": "already_processed", "sale_id": sale_id}), 200
    
    if not data:
        error_response = {"error": "No data received"}
        save_webhook_log({}, "error", error_response)
        return jsonify(error_response), 400
    
    # Log raw webhook data (IMPORTANT FOR DEBUGGING)
    logger.info(f"Raw Gumroad webhook received: {json.dumps(data, indent=2)}")
    
    # Extract customer info
    email = data.get('email')
    product_permalink = data.get('permalink', '')
    product_name = data.get('product_name', '')
    gumroad_license_key = data.get('license_key')
    sale_id = data.get('sale_id')
    
    # Extract tier/variant if available (Gumroad sends as variants[Tier])
    tier = data.get('variants[Tier]', '')
    
    # If no tier specified, default to Lifetime for this product
    if not tier:
        tier = 'Lifetime'
    
    # Log all extracted fields for debugging
    logger.info(f"Extracted fields - Email: {email}, Product: {product_permalink}, Tier: {tier}, License Key: {gumroad_license_key}, Sale ID: {sale_id}")
    
    # Basic validation
    if not email:
        error_response = {"error": "Email required"}
        save_webhook_log(data, "error", error_response)
        return jsonify(error_response), 400
    
    # CHECK FOR REFUND: If this is a refund webhook (refunded=true),
    # find and deactivate the license instead of creating a new one
    if data.get('refunded') == 'true':
        logger.info(f"Refund detected for license key {gumroad_license_key}")
        
        # Find our license by the Gumroad license key
        our_license_key = license_manager.find_license_by_source_key(gumroad_license_key)
        
        if our_license_key:
            refund_result = license_manager.handle_refund(our_license_key, 'gumroad_refund')
            response = {
                "status": "refund_processed",
                "our_license_key": our_license_key,
                "gumroad_license_key": gumroad_license_key,
                "message": "License refunded and deactivated"
            }
            save_webhook_log(data, "refund_success", response)
            logger.info(f"Successfully processed refund for {our_license_key}")
            return jsonify(response), 200
        else:
            error_response = {
                "status": "refund_failed",
                "error": "License not found",
                "gumroad_license_key": gumroad_license_key
            }
            save_webhook_log(data, "refund_failed", error_response)
            logger.warning(f"Refund webhook received but license not found for {gumroad_license_key}")
            return jsonify(error_response), 404
    
    # PURCHASE: If not a refund, process as new purchase
    # Create backup before modifying data (safety measure)
    try:
        logger.info("Creating pre-webhook backup...")
        backup_manager.create_backup('pre_webhook')
    except Exception as e:
        logger.warning(f"Failed to create backup (continuing anyway): {e}")
    
    # Determine duration based on tier first, then product
    # Priority: tier variant > product permalink > default
    if tier and tier in TIER_DURATIONS:
        duration_days = TIER_DURATIONS[tier]
        logger.info(f"Mapped tier '{tier}' to {duration_days} days")
    else:
        duration_days = PRODUCT_DURATIONS.get(product_permalink, 365)
        logger.info(f"Mapped product '{product_permalink}' to {duration_days} days")
    
    # Normalize Gumroad data into standardized purchase_info structure
    purchase_info = normalize_gumroad_purchase(data, duration_days, tier)
    purchase_info['expires_days'] = int(duration_days)
    
    logger.info(f"Normalized purchase info: {json.dumps(purchase_info, indent=2)}")
    
    # Check if user had a trial (conversion scenario)
    licenses = license_manager.load_licenses()
    had_trial = False
    trial_days_used = 0
    
    for lic_key, lic_data in licenses.items():
        if lic_data.get('email', '').lower() == email.lower() and license_manager.is_trial_license(lic_key):
            had_trial = True
            # Calculate trial usage
            try:
                created = datetime.fromisoformat(lic_data.get('created_date'))
                trial_days_used = (datetime.now() - created).days
            except:
                trial_days_used = 0
            break
    
    # Create License with structured purchase_info
    try:
        if had_trial:
            # Trial conversion - use special method
            logger.info(f"🔄 Converting trial to full license for {email}")
            
            # Generate new license key
            license_key = license_manager.generate_license_key()
            
            # Convert trial to full
            full_license = license_manager.convert_trial_to_full(
                email=email,
                new_license_key=license_key,
                purchase_info=purchase_info
            )
            
            if full_license:
                # Send upgrade email
                email_sent = email_service.send_upgrade_email(
                    to_email=email,
                    license_key=license_key,
                    trial_days_used=trial_days_used
                )
                
                response = {
                    "status": "success", 
                    "type": "trial_conversion",
                    "license_key": license_key,
                    "trial_days_used": trial_days_used,
                    "email_sent": email_sent
                }
                save_webhook_log(data, "success", response)
                logger.info(f"✅ Trial converted to full license for {email}")
                
                return jsonify(response), 200
            else:
                error_response = {"error": "Failed to convert trial"}
                save_webhook_log(data, "error", error_response)
                return jsonify(error_response), 500
        else:
            # New customer (no trial history)
            logger.info(f"ℹ️  New customer purchase: {email}")
            
            license_key = license_manager.create_license(
                email=email,
                expires_days=int(duration_days),
                license_key=None,
                purchase_info=purchase_info
            )
            
            if license_key:
                # Send welcome email
                email_sent = email_service.send_license_email(email, license_key, None)
                
                response = {
                    "status": "success",
                    "type": "new_purchase", 
                    "license_key": license_key,
                    "email_sent": email_sent
                }
                save_webhook_log(data, "success", response)
                logger.info(f"License created successfully for {email}")
                
                return jsonify(response), 200
            else:
                error_response = {"error": "Failed to create license"}
                save_webhook_log(data, "error", error_response)
                return jsonify(error_response), 500
            
    except Exception as e:
        logger.error(f"Exception processing webhook: {str(e)}", exc_info=True)
        error_response = {"error": str(e)}
        save_webhook_log(data, "exception", error_response)
        return jsonify(error_response), 500

@webhook_bp.route('/gumroad/test-refund', methods=['POST'])
def gumroad_test_refund():
    """
    TESTING ENDPOINT - Logs ALL webhook data for diagnostic purposes
    Gumroad sends refunds as updates to the purchase webhook with refunded=true flag
    This endpoint captures that data for testing
    Endpoint: POST /api/v1/webhooks/gumroad/test-refund
    """
    
    # Capture everything Gumroad sends
    data = request.form.to_dict() if request.form else request.get_json() or {}
    
    debug_record = {
        'timestamp': datetime.utcnow().isoformat(),
        'endpoint': 'test-refund',
        'method': request.method,
        'content_type': request.content_type,
        'all_form_data': dict(request.form) if request.form else {},
        'all_json_data': request.get_json() if request.is_json else {},
        'raw_data': data,
        'headers': dict(request.headers),
    }
    
    # Log to debug file
    try:
        with open(WEBHOOK_DEBUG_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(debug_record, default=str) + '\n')
        logger.info(f"Test webhook logged - check {WEBHOOK_DEBUG_LOG}")
    except Exception as e:
        logger.error(f"Failed to log test webhook: {e}")
    
    return jsonify({
        "status": "debug_logged",
        "message": f"Webhook data logged to {WEBHOOK_DEBUG_LOG}",
        "received_fields": list(data.keys()),
        "data_sample": {k: v for k, v in list(data.items())[:5]}
    }), 200

@webhook_bp.route('/gumroad/webhook-logs', methods=['GET'])
def gumroad_webhook_logs():
    """
    View diagnostic webhook logs
    Shows ALL webhooks received (purchases and refunds with refunded=true flag)
    """
    try:
        logs = []
        
        # Read from webhook_debug.jsonl (detailed logs)
        if os.path.exists(WEBHOOK_DEBUG_LOG):
            with open(WEBHOOK_DEBUG_LOG, 'r', encoding='utf-8') as f:
                for line in f.readlines()[-50:]:  # Last 50 entries
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass
        
        return jsonify({
            "total_logs": len(logs),
            "logs": logs,
            "instructions": {
                "step_1": "Use test endpoint to send data",
                "step_2": "POST to /api/v1/webhooks/gumroad/test-refund",
                "step_3": "Check response to see what fields were received",
                "step_4": "View full logs here (last 50 entries)"
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/gumroad/debug', methods=['GET'])
def gumroad_debug():
    """View recent webhook logs for debugging"""
    try:
        logs = []
        with open('webhook_logs.jsonl', 'r', encoding='utf-8') as f:
            for line in f.readlines()[-20:]:  # Last 20 entries
                logs.append(json.loads(line))
        return jsonify(logs), 200
    except FileNotFoundError:
        return jsonify({"message": "No logs yet"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# MICROSOFT STORE WEBHOOK HANDLERS
# ============================================================================

# Microsoft Store product SKU to duration mapping
MSSTORE_PRODUCT_DURATIONS = {
    # Add your MS Store SKUs here after publishing
    # Format: 'product_sku': duration_days
    "imgapp_lifetime": 36500,
    "imgapp_yearly": 365,
    "imgapp_monthly": 30,
}

# Microsoft Store tier mapping
MSSTORE_TIER_MAP = {
    "imgapp_lifetime": "Lifetime",
    "imgapp_yearly": "Yearly",
    "imgapp_monthly": "Monthly",
}


def verify_msstore_webhook(request_headers: dict, payload: bytes) -> tuple:
    """
    Verify Microsoft Store webhook authenticity.
    
    MS Store webhooks use Azure AD for authentication:
    1. Webhook contains a JWT in Authorization header
    2. Verify JWT signature against Microsoft's public keys
    3. Verify issuer and audience claims
    
    NOTE: In production, implement full JWT verification.
    For now, we verify using a shared client secret approach.
    
    Args:
        request_headers: HTTP request headers
        payload: Raw request body bytes
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # Get client secret from config
    client_secret = Config.MSSTORE_CLIENT_SECRET
    
    if not client_secret:
        logger.warning("MSSTORE_CLIENT_SECRET not configured - skipping verification")
        return True, None  # Allow in dev mode
    
    # Option 1: Check for secret in header (simple webhook secret)
    webhook_secret = request_headers.get('X-MS-Webhook-Secret', '')
    if webhook_secret:
        if hmac.compare_digest(webhook_secret, client_secret):
            return True, None
        else:
            return False, "Invalid webhook secret"
    
    # Option 2: Check for Azure AD JWT (production)
    auth_header = request_headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        # TODO: Implement full JWT verification with Azure AD
        # For now, log and allow (should implement before production)
        logger.warning("MS Store JWT verification not fully implemented - allowing webhook")
        return True, None
    
    # No authentication found
    logger.warning("No authentication found in MS Store webhook")
    return False, "Missing authentication"


def normalize_msstore_purchase(data: dict, duration_days: int, tier: str) -> dict:
    """
    Normalize Microsoft Store webhook data into standardized purchase_info structure.
    
    MS Store webhook payload structure (simplified):
    {
        "orderId": "unique-order-id",
        "lineItemId": "line-item-id",
        "productId": "product_sku",
        "skuId": "sku_variant",
        "beneficiary": {
            "userId": "ms_user_id",
            "identityType": "msa/aad"
        },
        "purchaser": {
            "userId": "purchaser_ms_user_id",
            "email": "purchaser@email.com"
        },
        "purchasedAt": "2024-01-01T00:00:00Z",
        "quantity": 1,
        "unitPrice": {"amount": "9.99", "currency": "USD"},
        "orderStatus": "Completed/Refunded/etc"
    }
    
    Args:
        data: Raw MS Store webhook data
        duration_days: License duration based on SKU
        tier: Mapped tier name
    
    Returns:
        dict: Standardized purchase_info structure
    """
    # Extract nested data safely
    beneficiary = data.get('beneficiary', {})
    purchaser = data.get('purchaser', {})
    unit_price = data.get('unitPrice', {})
    
    # Build standardized purchase info
    purchase_info = {
        'source': Platform.MSSTORE.value,
        'source_license_key': None,  # MS Store doesn't provide license keys
        'order_id': data.get('orderId'),  # MS Store uses orderId
        'sale_id': data.get('orderId'),  # Alias for compatibility
        'line_item_id': data.get('lineItemId'),
        'customer_id': beneficiary.get('userId'),
        'purchaser_id': purchaser.get('userId'),
        'product_id': data.get('productId'),
        'sku_id': data.get('skuId'),
        'product_name': data.get('productId', ''),  # Use product_id as name
        'tier': tier,
        'price': unit_price.get('amount'),
        'currency': unit_price.get('currency', 'USD').lower(),
        'purchase_date': data.get('purchasedAt', datetime.utcnow().isoformat()),
        'is_recurring': data.get('autoRenewing', False),
        'recurrence': 'subscription' if data.get('autoRenewing') else None,
        'subscription_id': data.get('subscriptionId'),
        'renewal_date': data.get('renewalDate'),
        'order_status': data.get('orderStatus'),
        'is_refunded': data.get('orderStatus') == 'Refunded',
        'refund_date': data.get('refundedAt'),
        'is_disputed': data.get('orderStatus') == 'Disputed',
        'is_test': data.get('isSandbox', False) or data.get('isTest', False),
        # MS Store specific fields
        'beneficiary_identity_type': beneficiary.get('identityType'),
        'quantity': data.get('quantity', 1),
    }
    
    return purchase_info


@webhook_bp.route('/msstore', methods=['POST'])
def msstore_webhook():
    """
    Handle Microsoft Store purchase webhooks.
    
    MS Store sends webhooks for:
    - New purchases (orderStatus: Completed)
    - Refunds (orderStatus: Refunded)
    - Subscription renewals
    - Subscription cancellations
    
    SECURITY: Verify webhook using Azure AD JWT or shared secret.
    """
    try:
        # Get raw payload for signature verification
        payload = request.get_data()
        data = request.get_json()
        
        if not data:
            error_response = {"error": "No data received"}
            save_webhook_log({'source': 'msstore'}, "error", error_response)
            return jsonify(error_response), 400
        
        # Log raw webhook data
        logger.info(f"Raw MS Store webhook received: {json.dumps(data, indent=2)}")
        
        # SECURITY: Verify webhook authenticity
        if Config.VERIFY_MSSTORE_WEBHOOK:
            is_valid, error_msg = verify_msstore_webhook(dict(request.headers), payload)
            
            if not is_valid:
                error_response = {"error": error_msg or "Webhook verification failed"}
                save_webhook_log({'source': 'msstore', 'verification_failed': True}, "security_error", error_response)
                logger.warning(f"MS Store webhook verification failed from IP: {request.remote_addr}")
                return jsonify(error_response), 403
        
        # Extract key fields
        order_id = data.get('orderId')
        order_status = data.get('orderStatus', '').lower()
        product_id = data.get('productId', '')
        
        # Get email from purchaser or beneficiary
        purchaser = data.get('purchaser', {})
        beneficiary = data.get('beneficiary', {})
        email = purchaser.get('email') or beneficiary.get('email')
        
        if not order_id:
            error_response = {"error": "Missing orderId"}
            save_webhook_log(data, "error", error_response)
            return jsonify(error_response), 400
        
        # IDEMPOTENCY: Check if we already processed this order
        existing = license_manager.find_license_by_platform_id(Platform.MSSTORE.value, order_id)
        if existing and order_status == 'completed':
            logger.info(f"Duplicate MS Store webhook for order {order_id} - already processed")
            return jsonify({"status": "already_processed", "order_id": order_id}), 200
        
        # Handle different order statuses
        if order_status == 'refunded':
            return _handle_msstore_refund(data, order_id)
        elif order_status == 'completed':
            return _handle_msstore_purchase(data, email, order_id, product_id)
        elif order_status == 'cancelled':
            return _handle_msstore_cancellation(data, order_id)
        else:
            # Log unknown status but return success (don't block webhooks)
            logger.warning(f"Unknown MS Store order status: {order_status}")
            return jsonify({"status": "acknowledged", "order_status": order_status}), 200
            
    except Exception as e:
        logger.error(f"MS Store webhook error: {e}")
        return jsonify({"error": "Webhook processing failed", "message": str(e)}), 500


def _handle_msstore_purchase(data: dict, email: str, order_id: str, product_id: str):
    """Handle new MS Store purchase"""
    
    if not email:
        # MS Store purchases might not always include email
        # Generate a placeholder email based on MS user ID
        beneficiary = data.get('beneficiary', {})
        ms_user_id = beneficiary.get('userId', 'unknown')
        email = f"msstore_{ms_user_id}@placeholder.msstore"
        logger.warning(f"No email in MS Store webhook, using placeholder: {email}")
    
    # Determine duration based on product SKU
    duration_days = MSSTORE_PRODUCT_DURATIONS.get(product_id, 36500)  # Default lifetime
    tier = MSSTORE_TIER_MAP.get(product_id, 'Lifetime')
    
    logger.info(f"MS Store purchase: product={product_id}, tier={tier}, duration={duration_days} days")
    
    # Normalize purchase data
    purchase_info = normalize_msstore_purchase(data, duration_days, tier)
    purchase_info['expires_days'] = duration_days
    
    # Create backup before modifying
    try:
        backup_manager.create_backup('pre_msstore_webhook')
    except Exception as e:
        logger.warning(f"Failed to create backup: {e}")
    
    # Check for existing trial (conversion scenario)
    trials = license_manager.load_trials()
    had_trial = False
    trial_days_used = 0
    
    for trial_key, trial_data in trials.items():
        if trial_data.get('email', '').lower() == email.lower():
            had_trial = True
            try:
                created = datetime.fromisoformat(trial_data.get('created_date'))
                trial_days_used = (datetime.now() - created).days
            except:
                trial_days_used = 0
            break
    
    # Create license
    try:
        license_key = license_manager.generate_license_key()
        
        if had_trial:
            # Convert trial to full license
            full_license = license_manager.convert_trial_to_full(
                email=email,
                new_license_key=license_key,
                purchase_info=purchase_info
            )
        else:
            # Create new license
            license_key = license_manager.create_license(
                email=email,
                expires_days=duration_days,
                license_key=license_key,
                purchase_info=purchase_info,
                platform=Platform.MSSTORE
            )
        
        if license_key:
            # Send welcome email
            try:
                email_service.send_welcome_email(
                    to_email=email,
                    license_key=license_key
                )
            except Exception as e:
                logger.warning(f"Failed to send MS Store welcome email: {e}")
            
            response = {
                "status": "success",
                "type": "trial_conversion" if had_trial else "new_purchase",
                "license_key": license_key,
                "email": email,
                "order_id": order_id,
                "product_id": product_id,
                "tier": tier,
                "platform": Platform.MSSTORE.value
            }
            save_webhook_log(data, "success", response)
            return jsonify(response), 200
        else:
            error_response = {"error": "Failed to create license"}
            save_webhook_log(data, "error", error_response)
            return jsonify(error_response), 500
            
    except Exception as e:
        logger.error(f"MS Store purchase processing failed: {e}")
        error_response = {"error": str(e)}
        save_webhook_log(data, "error", error_response)
        return jsonify(error_response), 500


def _handle_msstore_refund(data: dict, order_id: str):
    """Handle MS Store refund"""
    logger.info(f"Processing MS Store refund for order: {order_id}")
    
    # Use platform-agnostic deactivation
    result = license_manager.deactivate_by_platform_id(
        platform=Platform.MSSTORE.value,
        transaction_id=order_id,
        reason='msstore_refund'
    )
    
    if result.get('success'):
        response = {
            "status": "refund_processed",
            "order_id": order_id,
            "license_key": result.get('license_key'),
            "message": "License refunded and deactivated"
        }
        save_webhook_log(data, "refund_success", response)
        return jsonify(response), 200
    else:
        # License not found - might be already refunded or never existed
        error_response = {
            "status": "refund_warning",
            "order_id": order_id,
            "error": result.get('error'),
            "message": result.get('message', 'License not found for this order')
        }
        save_webhook_log(data, "refund_warning", error_response)
        # Return 200 to acknowledge webhook (don't want MS Store to retry)
        return jsonify(error_response), 200


def _handle_msstore_cancellation(data: dict, order_id: str):
    """Handle MS Store subscription cancellation"""
    logger.info(f"Processing MS Store subscription cancellation for order: {order_id}")
    
    # Find the license
    license_key = license_manager.find_license_by_platform_id(Platform.MSSTORE.value, order_id)
    
    if license_key:
        # For cancellations, we might want to let the license expire naturally
        # rather than immediately deactivating
        response = {
            "status": "cancellation_acknowledged",
            "order_id": order_id,
            "license_key": license_key,
            "message": "Subscription cancellation noted - license will expire at end of period"
        }
        save_webhook_log(data, "cancellation", response)
        return jsonify(response), 200
    else:
        response = {
            "status": "cancellation_warning",
            "order_id": order_id,
            "message": "License not found for this subscription"
        }
        save_webhook_log(data, "cancellation_warning", response)
        return jsonify(response), 200


@webhook_bp.route('/msstore/test', methods=['POST'])
def msstore_test_webhook():
    """Test endpoint for MS Store webhook simulation (development only)"""
    if not Config.DEBUG:
        return jsonify({"error": "Test endpoint disabled in production"}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Add test flag
        data['isTest'] = True
        data['isSandbox'] = True
        
        # Forward to main handler
        logger.info(f"MS Store test webhook: {json.dumps(data, indent=2)}")
        
        return msstore_webhook()
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# TRIAL SYSTEM ENDPOINTS
# ============================================================================

@webhook_bp.route('/trial/check-eligibility', methods=['POST'])
def trial_check_eligibility():
    """Check if user is eligible for a free trial
    
    Request body:
        {
            "email": "user@example.com",
            "hardware_id": "ABC123XYZ"
        }
    
    Response:
        {
            "eligible": true/false,
            "reason": "trial_already_used_email" | "trial_already_used_device" | null,
            "message": "..."
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        email = data.get('email')
        hardware_id = data.get('hardware_id')
        
        if not email or not hardware_id:
            return jsonify({
                "error": "Missing required fields",
                "required": ["email", "hardware_id"]
            }), 400
        
        # Check eligibility
        result = license_manager.check_trial_eligibility(email, hardware_id)
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Trial eligibility check failed: {e}")
        return jsonify({
            "error": "Failed to check eligibility",
            "message": str(e)
        }), 500

@webhook_bp.route('/trial/create', methods=['POST'])
@webhook_bp.route('/trial/create', methods=['POST'])
def trial_create():
    """Create a new trial license
    
    Request body:
        {
            "email": "user@example.com",
            "hardware_id": "ABC123XYZ",
            "device_name": "MacBook Pro" (optional)
        }
    
    Response:
        {
            "success": true,
            "license_key": "IW-...",
            "expires": "2025-12-15T...",
            "message": "Trial license created successfully"
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        email = data.get('email')
        hardware_id = data.get('hardware_id')
        device_name = data.get('device_name', 'Unknown Device')
        
        if not email or not hardware_id:
            return jsonify({
                "error": "Missing required fields",
                "required": ["email", "hardware_id"]
            }), 400
        
        logger.info(f"📝 Trial creation request: email={email}, hardware_id={hardware_id}")
        
        # Create trial license
        result = license_manager.create_trial_license(email, hardware_id, device_name)
        
        if result['success']:
            logger.info(f"✅ Trial created successfully: {result['license_key'][:8]}...")
            # Send trial-specific activation email
            try:
                email_service.send_trial_email(email, result['license_key'])
            except Exception as e:
                logger.warning(f"Failed to send trial email: {e}")
            
            return jsonify(result), 201
        else:
            # Trial creation was rejected
            logger.warning(f"⚠️ Trial creation rejected: {result.get('error')} - {result.get('message')}")
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Trial creation failed: {e}")
        return jsonify({
            "error": "Failed to create trial",
            "message": str(e)
        }), 500

@webhook_bp.route('/trial/status/<license_key>', methods=['GET'])
def trial_status(license_key):
    """Get trial license status
    
    Response:
        {
            "success": true,
            "is_trial": true,
            "is_active": true,
            "expires": "2025-12-15T...",
            "email": "user@example.com",
            "device_name": "MacBook Pro"
        }
    """
    try:
        licenses = license_manager.load_licenses()
        
        if license_key not in licenses:
            return jsonify({
                "error": "License not found"
            }), 404
        
        license_data = licenses[license_key]
        is_trial = license_manager.is_trial_license(license_key)
        
        return jsonify({
            "success": True,
            "is_trial": is_trial,
            "is_active": license_data.get('is_active'),
            "expires": license_data.get('expiry_date'),
            "email": license_data.get('email'),
            "device_name": license_data.get('device_name'),
            "hardware_id": license_data.get('hardware_id')
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get trial status: {e}")
        return jsonify({
            "error": "Failed to get status",
            "message": str(e)
        }), 500

@webhook_bp.route('/license/offline-check/<license_key>', methods=['POST'])
def license_offline_check(license_key):
    """Check if a license can be used offline (for client-side grace period validation)
    
    Request body:
        {
            "email": "user@example.com",
            "hardware_id": "ABC123XYZ"
        }
    
    Response:
        {
            "can_use_offline": true/false,
            "is_trial": false,
            "days_since_last_validation": 2,
            "grace_period_remaining": 1,
            "message": "..."
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        email = data.get('email')
        hardware_id = data.get('hardware_id')
        
        if not email or not hardware_id:
            return jsonify({
                "error": "Missing required fields",
                "required": ["email", "hardware_id"]
            }), 400
        
        licenses = license_manager.load_licenses()
        
        if license_key not in licenses:
            return jsonify({
                "error": "License not found"
            }), 404
        
        license_data = licenses[license_key]
        is_trial = license_manager.is_trial_license(license_key)
        
        # Trials NEVER work offline
        if is_trial:
            return jsonify({
                "can_use_offline": False,
                "is_trial": True,
                "message": "Trial licenses require internet connection"
            }), 200
        
        # Check grace period for paid licenses
        last_validation = license_data.get('last_validation')
        
        if not last_validation:
            return jsonify({
                "can_use_offline": False,
                "is_trial": False,
                "message": "License must be activated online first"
            }), 200
        
        last_val_date = datetime.fromisoformat(last_validation)
        days_since = (datetime.now() - last_val_date).days
        grace_remaining = max(0, 3 - days_since)
        
        can_use = days_since <= 3
        
        return jsonify({
            "can_use_offline": can_use,
            "is_trial": False,
            "days_since_last_validation": days_since,
            "grace_period_remaining": grace_remaining,
            "message": f"{'Offline use available' if can_use else 'Please connect to internet to validate'}"
        }), 200
        
    except Exception as e:
        logger.error(f"Offline check failed: {e}")
        return jsonify({
            "error": "Failed to check offline status",
            "message": str(e)
        }), 500