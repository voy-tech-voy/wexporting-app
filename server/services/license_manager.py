import json
import os
import logging
import secrets
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
from config.settings import Config

logger = logging.getLogger(__name__)

# Thread locks for file operations (prevents race conditions)
_licenses_lock = threading.Lock()
_trials_lock = threading.Lock()
_purchases_lock = threading.Lock()


class Platform(str, Enum):
    """
    Supported purchase/license platforms.
    
    Each platform has its own webhook handler and purchase normalization.
    The license system is platform-agnostic - all platforms produce
    the same license structure.
    """
    GUMROAD = "gumroad"
    MSSTORE = "msstore"       # Microsoft Store
    STRIPE = "stripe"         # Future: Direct Stripe integration
    DIRECT = "direct"         # Manual/admin-created licenses
    TRIAL = "trial"           # Free trials
    
    @classmethod
    def is_valid(cls, platform: str) -> bool:
        """Check if platform string is valid"""
        return platform in [p.value for p in cls]
    
    @classmethod
    def all_values(cls) -> List[str]:
        """Get all platform values"""
        return [p.value for p in cls]


def get_platform_sale_id_field(platform: str) -> str:
    """
    Get the field name used for unique transaction ID per platform.
    
    Each platform uses different field names for their unique transaction ID:
    - Gumroad: sale_id
    - Microsoft Store: order_id or transaction_id  
    - Stripe: payment_intent_id
    
    Returns:
        str: The field name for this platform's unique transaction ID
    """
    platform_id_fields = {
        Platform.GUMROAD.value: 'sale_id',
        Platform.MSSTORE.value: 'order_id',
        Platform.STRIPE.value: 'payment_intent_id',
        Platform.DIRECT.value: 'admin_ref',
        Platform.TRIAL.value: 'trial_id',
    }
    return platform_id_fields.get(platform, 'sale_id')


class LicenseManager:
    def __init__(self):
        self.license_file = Config.LICENSES_FILE
        self.trials_file = Config.TRIALS_FILE
        self.purchases_file = os.path.join(os.path.dirname(self.license_file), 'purchases.jsonl')
        self.ensure_license_file()
        self.ensure_trials_file()
    
    def ensure_license_file(self):
        """Ensure license file exists"""
        if not os.path.exists(self.license_file):
            os.makedirs(os.path.dirname(self.license_file), exist_ok=True)
            with open(self.license_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def ensure_trials_file(self):
        """Ensure trials.json file exists"""
        if not os.path.exists(self.trials_file):
            os.makedirs(os.path.dirname(self.trials_file), exist_ok=True)
            with open(self.trials_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def load_licenses(self):
        """Load licenses from file with thread safety"""
        with _licenses_lock:
            try:
                with open(self.license_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load licenses: {e}")
                return {}
    
    def save_licenses(self, licenses):
        """Save licenses to file with thread safety and atomic write"""
        with _licenses_lock:
            try:
                # Write to temp file first, then rename (atomic on most filesystems)
                temp_file = self.license_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(licenses, f, indent=2)
                
                # Atomic rename
                os.replace(temp_file, self.license_file)
                return True
            except Exception as e:
                logger.error(f"Failed to save licenses: {e}")
                # Clean up temp file if it exists
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
                return False
    
    def load_trials(self):
        """Load trials from file with thread safety"""
        with _trials_lock:
            try:
                with open(self.trials_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load trials: {e}")
                return {}
    
    def save_trials(self, trials):
        """Save trials to file with thread safety and atomic write"""
        with _trials_lock:
            try:
                # Write to temp file first, then rename (atomic on most filesystems)
                temp_file = self.trials_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(trials, f, indent=2)
                
                # Atomic rename
                os.replace(temp_file, self.trials_file)
                return True
            except Exception as e:
                logger.error(f"Failed to save trials: {e}")
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
                return False
    
    def generate_license_key(self):
        """Generate a unique license key"""
        timestamp = str(int(datetime.now().timestamp()))
        random_part = secrets.token_hex(8)
        return f"IW-{timestamp[-6:]}-{random_part.upper()[:8]}"
    
    def create_license(self, email, expires_days=365, license_key=None, purchase_info=None, platform=None):
        """Create a new license with optional purchase tracking
        
        Args:
            email: Customer email
            expires_days: License duration in days
            license_key: Specific license key (optional, generates if not provided)
            purchase_info: Dict with purchase metadata for audit logging (optional):
                {
                    'source': 'gumroad' | 'msstore' | 'stripe' | 'direct' | 'trial',
                    'source_license_key': License key from payment platform,
                    'sale_id': Unique transaction ID (platform-specific field name),
                    'customer_id': Platform-specific customer ID,
                    'product_id': Platform product ID,
                    'product_name': Product display name,
                    'tier': Subscription tier,
                    'price': Purchase price,
                    'currency': Currency code,
                    'purchase_date': ISO datetime,
                    'is_recurring': Boolean,
                    'subscription_id': For subscriptions,
                    'is_refunded': Boolean,
                    'is_disputed': Boolean,
                    'is_test': Boolean
                }
            platform: Platform enum value or string (auto-detected from purchase_info if not provided)
        """
        try:
            licenses = self.load_licenses()
            
            if not license_key:
                license_key = self.generate_license_key()
            
            # Check if license key already exists
            if license_key in licenses:
                logger.warning(f"License key {license_key} already exists")
                return license_key

            expiry_date = datetime.now() + timedelta(days=expires_days)
            
            # Determine platform - explicit > purchase_info.source > default
            resolved_platform = None
            if platform:
                resolved_platform = platform.value if isinstance(platform, Platform) else platform
            elif purchase_info and purchase_info.get('source'):
                resolved_platform = purchase_info.get('source')
            else:
                resolved_platform = Platform.DIRECT.value
            
            # Validate platform
            if not Platform.is_valid(resolved_platform):
                logger.warning(f"Unknown platform '{resolved_platform}', defaulting to 'direct'")
                resolved_platform = Platform.DIRECT.value
            
            # Get platform-specific transaction ID field
            platform_id_field = get_platform_sale_id_field(resolved_platform)
            platform_transaction_id = purchase_info.get(platform_id_field) if purchase_info else None
            
            # Core license fields - LEAN & VALIDATION-FOCUSED (10 fields)
            license_data = {
                'email': email,
                'created_date': datetime.now().isoformat(),
                'expiry_date': expiry_date.isoformat(),
                'is_active': True,
                'hardware_id': None,
                'device_name': None,
                'last_validation': None,
                'validation_count': 0,
                'source_license_key': purchase_info.get('source_license_key') if purchase_info else None,
                # NEW: Platform tracking for multi-store support
                'platform': resolved_platform,
                'platform_transaction_id': platform_transaction_id,  # e.g., sale_id, order_id
            }
            
            licenses[license_key] = license_data
            
            if self.save_licenses(licenses):
                logger.info(f"Created license {license_key} for {email} (platform: {resolved_platform})")
                
                # Log full purchase details separately for audit trail
                if purchase_info:
                    self.log_purchase(license_key, purchase_info)
                
                return license_key
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to create license: {e}")
            return None
    
    def log_purchase(self, license_key, purchase_info):
        """Log detailed purchase information to audit trail (purchases.jsonl) with thread safety"""
        with _purchases_lock:
            try:
                purchase_record = {
                    'timestamp': datetime.now().isoformat(),
                    'license_key': license_key,
                    **purchase_info  # Unpack all purchase details
                }
                
                with open(self.purchases_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(purchase_record) + '\n')
                
                logger.info(f"Purchase logged for license {license_key}")
                return True
            except Exception as e:
                logger.error(f"Failed to log purchase: {e}")
                return False
    
    def check_trial_eligibility(self, email, hardware_id):
        """Check if user is eligible for a trial (abuse prevention)
        
        Args:
            email: User's email address
            hardware_id: Device hardware ID
        
        Returns:
            dict: {'eligible': bool, 'reason': str, 'message': str}
        """
        try:
            # Check trials.json for existing trials
            trials = self.load_trials()
            now = datetime.now()
            
            # Check if trial already exists for this email
            for trial_key, trial_data in trials.items():
                if trial_data.get('email') == email:
                    # Check is_active flag first (most important)
                    is_active = trial_data.get('is_active', False)
                    
                    if is_active:
                        logger.warning(f"❌ Trial creation rejected: Email {email} has active trial {trial_key[:8]}...")
                        return {
                            'eligible': False,
                            'reason': 'trial_already_used_email',
                            'message': 'You have already used your free trial'
                        }
                    
                    # Also check expiry date as backup
                    try:
                        expiry = datetime.fromisoformat(trial_data['expiry_date'])
                        if now < expiry:
                            logger.warning(f"❌ Trial creation rejected: Email {email} has non-expired trial {trial_key[:8]}...")
                            return {
                                'eligible': False,
                                'reason': 'trial_already_used_email',
                                'message': 'You have already used your free trial'
                            }
                    except ValueError as e:
                        logger.error(f"Invalid expiry_date format for trial {trial_key}: {e}")
            
            # Check if trial already exists for this hardware_id
            for trial_key, trial_data in trials.items():
                if trial_data.get('hardware_id') == hardware_id:
                    # Check is_active flag first (most important)
                    is_active = trial_data.get('is_active', False)
                    
                    if is_active:
                        logger.warning(f"❌ Trial creation rejected: Hardware {hardware_id} has active trial {trial_key[:8]}...")
                        return {
                            'eligible': False,
                            'reason': 'trial_already_used_device',
                            'message': 'You already used your free trial.'
                        }
                    
                    # Also check expiry date as backup
                    try:
                        expiry = datetime.fromisoformat(trial_data['expiry_date'])
                        if now < expiry:
                            logger.warning(f"❌ Trial creation rejected: Hardware {hardware_id} has non-expired trial {trial_key[:8]}...")
                            return {
                                'eligible': False,
                                'reason': 'trial_already_used_device',
                                'message': 'You already used your free trial.'
                            }
                    except ValueError as e:
                        logger.error(f"Invalid expiry_date format for trial {trial_key}: {e}")
            
            # Also check if user already has a full license
            licenses = self.load_licenses()
            for license_key, license_data in licenses.items():
                if license_data.get('email') == email and license_data.get('is_active'):
                    # Check if it's NOT a trial (full license)
                    try:
                        created = datetime.fromisoformat(license_data['created_date'])
                        expiry = datetime.fromisoformat(license_data['expiry_date'])
                        days_diff = (expiry - created).days
                        
                        if days_diff > 1:  # It's a full license, not a trial
                            logger.warning(f"❌ Trial creation rejected: Email {email} already has full license {license_key[:8]}...")
                            return {
                                'eligible': False,
                                'reason': 'already_has_license',
                                'message': 'You already have a full license. Please log in with your license key.'
                            }
                    except ValueError as e:
                        logger.error(f"Invalid date format for license {license_key}: {e}")
            
            logger.info(f"✅ Trial eligibility check PASSED: {email} (hardware: {hardware_id})")
            return {
                'eligible': True,
                'message': 'User is eligible for a trial'
            }
            
        except Exception as e:
            logger.error(f"Error checking trial eligibility: {e}")
            return {
                'eligible': False,
                'reason': 'check_failed',
                'message': 'Failed to verify trial eligibility'
            }
    
    def create_trial_license(self, email, hardware_id, device_name="Unknown"):
        """Create a 1-day trial license (immediately bound to device)
        
        Saves to trials.json (NOT licenses.json)
        
        Args:
            email: User's email address
            hardware_id: Device hardware ID (required for trial)
            device_name: Device name for identification
        
        Returns:
            dict: {'success': bool, 'license_key': str, 'error': str}
        """
        try:
            # Check eligibility first - THIS IS CRITICAL
            eligibility = self.check_trial_eligibility(email, hardware_id)
            if not eligibility['eligible']:
                logger.error(f"❌ Trial creation REJECTED: {email} - Reason: {eligibility.get('reason')}")
                logger.error(f"   Message: {eligibility.get('message')}")
                return {
                    'success': False,
                    'error': eligibility['reason'],
                    'message': eligibility['message']
                }
            
            # Load trials from trials.json (NOT licenses.json)
            trials = self.load_trials()
            license_key = self.generate_license_key()
            
            # Trial expires in 7 days
            expiry_date = datetime.now() + timedelta(days=7)
            
            # Create trial license (immediately bound to device)
            trial_data = {
                'email': email,
                'created_date': datetime.now().isoformat(),
                'expiry_date': expiry_date.isoformat(),
                'is_active': True,
                'hardware_id': hardware_id,  # Immediately bound
                'device_name': device_name,
                'last_validation': datetime.now().isoformat(),
                'validation_count': 0,
                'source_license_key': None,  # Trials don't have external source
                'converted_to_full': False
            }
            
            # Save to trials.json
            trials[license_key] = trial_data
            
            if self.save_trials(trials):
                logger.info(f"✅ Created trial license {license_key[:8]}... for {email} on device {hardware_id}")
                logger.info(f"   Trial saved to trials.json (expires: {expiry_date.isoformat()})")
                
                # Log trial creation to audit trail
                trial_info = {
                    'source': 'trial',
                    'is_trial': True,
                    'product_name': 'ImgApp Trial',
                    'tier': 'trial',
                    'price': 0,
                    'currency': 'USD',
                    'purchase_date': datetime.now().isoformat(),
                    'is_recurring': False
                }
                self.log_purchase(license_key, trial_info)
                
                return {
                    'success': True,
                    'license_key': license_key,
                    'expires': expiry_date.isoformat(),
                    'message': 'Trial license created successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'failed_to_save',
                    'message': 'Failed to save trial license'
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to create trial license: {e}")
            return {
                'success': False,
                'error': 'creation_failed',
                'message': f'Failed to create trial license: {str(e)}'
            }
    
    def is_trial_license(self, license_key):
        """Check if a license is a trial license
        
        Args:
            license_key: License key to check
        
        Returns:
            bool: True if trial, False otherwise
        """
        try:
            licenses = self.load_licenses()
            if license_key not in licenses:
                return False
            
            license_data = licenses[license_key]
            created = datetime.fromisoformat(license_data['created_date'])
            expiry = datetime.fromisoformat(license_data['expiry_date'])
            days_diff = (expiry - created).days
            
            # Trial licenses have 7-day duration
            return days_diff <= 7
        except:
            return False
    
    def validate_license(self, email, license_key, hardware_id, device_name="Unknown", is_offline=False):
        """Validate a license with offline support and trial restrictions
        
        Args:
            email: User's email
            license_key: License key to validate
            hardware_id: Device hardware ID
            device_name: Device name
            is_offline: True if validating offline (grace period for paid licenses only)
        
        Returns:
            dict: Validation result
        """
        try:
            licenses = self.load_licenses()
            trials = self.load_trials()
            
            # Check both licenses.json and trials.json
            license_data = None
            is_trial = False
            
            if license_key in licenses:
                license_data = licenses[license_key]
                is_trial = False
            elif license_key in trials:
                license_data = trials[license_key]
                is_trial = True
            else:
                return {'success': False, 'error': 'invalid_license'}
            
            # Check if this is a converted trial
            if license_data.get('converted_to_full'):
                full_key = license_data.get('full_license_key', 'your full license key')
                return {
                    'success': False,
                    'error': 'trial_converted',
                    'message': f'Your trial has been upgraded to a full license. Please use your full license key sent to {email}.'
                }
            
            # Check if license is active
            if not license_data.get('is_active', False):
                return {'success': False, 'error': 'license_deactivated'}
            
            # If this is a full license (not trial), deactivate any active trials for this email
            if not is_trial:
                self._deactivate_trial_for_email(email)
            
            # Check email match
            if license_data['email'] != email:
                return {'success': False, 'error': 'email_mismatch'}
            
            # Check expiry
            expiry_date = datetime.fromisoformat(license_data['expiry_date'])
            if datetime.now() > expiry_date:
                return {'success': False, 'error': 'license_expired'}
            
            # TRIAL RESTRICTION: No offline validation for trials
            if is_offline and is_trial:
                return {
                    'success': False,
                    'error': 'trial_requires_online',
                    'message': 'Trial licenses require internet connection for validation'
                }
            
            # OFFLINE GRACE PERIOD: For paid licenses only (3 days)
            if is_offline:
                last_validation = license_data.get('last_validation')
                if last_validation:
                    last_val_date = datetime.fromisoformat(last_validation)
                    days_since_validation = (datetime.now() - last_val_date).days
                    
                    if days_since_validation > 3:
                        return {
                            'success': False,
                            'error': 'offline_grace_expired',
                            'message': 'Please connect to the internet to validate your license'
                        }
                else:
                    # No previous validation - must validate online first
                    return {
                        'success': False,
                        'error': 'requires_online_validation',
                        'message': 'First-time activation requires internet connection'
                    }
            
            # Check hardware binding
            stored_hardware_id = license_data.get('hardware_id')
            if stored_hardware_id is None:
                # First activation - bind to this device
                license_data['hardware_id'] = hardware_id
                license_data['device_name'] = device_name
                logger.info(f"Bound license {license_key} to device {hardware_id}")
            elif stored_hardware_id != hardware_id:
                return {
                    'success': False, 
                    'error': 'bound_to_other_device',
                    'bound_device': license_data.get('device_name', 'Unknown Device')
                }
            
            # Update validation info (only if online)
            if not is_offline:
                license_data['last_validation'] = datetime.now().isoformat()
                license_data['validation_count'] = license_data.get('validation_count', 0) + 1
                
                # Save to correct file based on license type
                if is_trial:
                    trials[license_key] = license_data
                    self.save_trials(trials)
                else:
                    licenses[license_key] = license_data
                    self.save_licenses(licenses)
            
            return {
                'success': True,
                'message': 'License validated successfully',
                'expires': license_data['expiry_date'],
                'is_trial': is_trial
            }
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {'success': False, 'error': 'validation_failed'}
    
    def transfer_license(self, email, license_key, new_hardware_id, new_device_name="Unknown"):
        """Transfer license to a new device"""
        try:
            licenses = self.load_licenses()
            
            if license_key not in licenses:
                return {'success': False, 'error': 'invalid_license'}
            
            license_data = licenses[license_key]
            
            if license_data['email'] != email:
                return {'success': False, 'error': 'email_mismatch'}
            
            # Update device binding
            old_device = license_data.get('device_name', 'Unknown Device')
            license_data['hardware_id'] = new_hardware_id
            license_data['device_name'] = new_device_name
            license_data['last_validation'] = datetime.now().isoformat()
            
            licenses[license_key] = license_data
            self.save_licenses(licenses)
            
            logger.info(f"Transferred license {license_key} from {old_device} to {new_device_name}")
            
            return {
                'success': True,
                'message': f'License transferred to {new_device_name}'
            }
            
        except Exception as e:
            logger.error(f"Transfer error: {e}")
            return {'success': False, 'error': 'transfer_failed'}
    
    def find_license_by_source_key(self, source_license_key):
        """Find our license key by Gumroad/platform license key
        
        Args:
            source_license_key: The license key from payment platform (e.g., Gumroad)
        
        Returns:
            str: Our license key or None if not found
        """
        try:
            licenses = self.load_licenses()
            for our_key, license_data in licenses.items():
                if license_data.get('source_license_key') == source_license_key:
                    return our_key
            return None
        except Exception as e:
            logger.error(f"Error finding license by source key: {e}")
            return None
    
    def find_license_by_sale_id(self, sale_id):
        """Find our license key by Gumroad sale_id (idempotency check)
        
        Args:
            sale_id: The sale_id from Gumroad webhook
        
        Returns:
            str: Our license key or None if not found
        """
        try:
            licenses = self.load_licenses()
            for our_key, license_data in licenses.items():
                # Check in purchase_info.sale_id
                purchase_info = license_data.get('purchase_info', {})
                if purchase_info.get('sale_id') == sale_id:
                    return our_key
                # Also check legacy format (direct sale_id field)
                if license_data.get('sale_id') == sale_id:
                    return our_key
            return None
        except Exception as e:
            logger.error(f"Error finding license by sale_id: {e}")
            return None
    
    def find_license_by_platform_id(self, platform: str, transaction_id: str) -> Optional[str]:
        """
        Find license by platform-specific transaction ID.
        
        This is the platform-agnostic lookup method that works across all platforms.
        Each platform uses different ID fields:
        - Gumroad: sale_id
        - MS Store: order_id
        - Stripe: payment_intent_id
        
        Args:
            platform: Platform name ('gumroad', 'msstore', 'stripe', etc.)
            transaction_id: The platform's unique transaction identifier
        
        Returns:
            str: Our license key or None if not found
        """
        try:
            if not transaction_id:
                return None
                
            licenses = self.load_licenses()
            
            for our_key, license_data in licenses.items():
                # Check platform match
                license_platform = license_data.get('platform', '')
                if license_platform != platform:
                    continue
                
                # Check platform_transaction_id (new field)
                if license_data.get('platform_transaction_id') == transaction_id:
                    return our_key
                
                # Legacy support: Check old field names based on platform
                id_field = get_platform_sale_id_field(platform)
                if license_data.get(id_field) == transaction_id:
                    return our_key
                
                # Also check in purchase_info for audit-logged data
                purchase_info = license_data.get('purchase_info', {})
                if purchase_info.get(id_field) == transaction_id:
                    return our_key
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding license by platform ID: {e}")
            return None
    
    def find_licenses_by_platform(self, platform: str) -> Dict[str, Dict]:
        """
        Find all licenses from a specific platform.
        
        Useful for:
        - Platform-specific analytics
        - Migration operations
        - Debugging platform integrations
        
        Args:
            platform: Platform name ('gumroad', 'msstore', 'stripe', etc.)
        
        Returns:
            Dict[str, Dict]: Dictionary of {license_key: license_data} for matching platform
        """
        try:
            licenses = self.load_licenses()
            platform_licenses = {}
            
            for license_key, license_data in licenses.items():
                # Check explicit platform field
                if license_data.get('platform') == platform:
                    platform_licenses[license_key] = license_data
                    continue
                
                # Legacy fallback: Check source in purchase audit log
                purchase_info = license_data.get('purchase_info', {})
                if purchase_info.get('source') == platform:
                    platform_licenses[license_key] = license_data
            
            return platform_licenses
            
        except Exception as e:
            logger.error(f"Error finding licenses by platform: {e}")
            return {}
    
    def deactivate_by_platform_id(self, platform: str, transaction_id: str, reason: str = "platform_refund") -> Dict[str, Any]:
        """
        Deactivate license by platform-specific transaction ID.
        
        Used primarily for refund webhooks from any platform.
        
        Args:
            platform: Platform name ('gumroad', 'msstore', 'stripe', etc.)
            transaction_id: The platform's unique transaction identifier
            reason: Reason for deactivation (e.g., 'gumroad_refund', 'msstore_refund')
        
        Returns:
            dict: {'success': bool, 'license_key': str, 'error': str}
        """
        try:
            # Find the license first
            license_key = self.find_license_by_platform_id(platform, transaction_id)
            
            if not license_key:
                return {
                    'success': False,
                    'error': 'license_not_found',
                    'message': f'No license found for {platform} transaction: {transaction_id}'
                }
            
            # Deactivate using existing method
            result = self.handle_refund(license_key, reason)
            
            if result.get('success'):
                logger.info(f"Deactivated license {license_key} for {platform} transaction {transaction_id}")
                result['license_key'] = license_key
                result['platform'] = platform
                result['transaction_id'] = transaction_id
            
            return result
            
        except Exception as e:
            logger.error(f"Error deactivating by platform ID: {e}")
            return {
                'success': False,
                'error': 'deactivation_failed',
                'message': str(e)
            }
    
    def migrate_existing_licenses_platform(self) -> Dict[str, Any]:
        """
        Migrate existing licenses to include platform field.
        
        Call this once to update licenses that were created before
        platform tracking was added. Safe to run multiple times.
        
        Returns:
            dict: {'migrated': int, 'already_migrated': int, 'errors': int}
        """
        try:
            licenses = self.load_licenses()
            stats = {'migrated': 0, 'already_migrated': 0, 'errors': 0}
            
            for license_key, license_data in licenses.items():
                try:
                    # Skip if already has platform field
                    if license_data.get('platform'):
                        stats['already_migrated'] += 1
                        continue
                    
                    # Detect platform from existing data
                    source = None
                    
                    # Check source_license_key format (Gumroad keys have specific format)
                    source_key = license_data.get('source_license_key')
                    if source_key:
                        # Gumroad license keys are typically 32-35 chars
                        if len(source_key) == 32 or len(source_key) == 35:
                            source = Platform.GUMROAD.value
                    
                    # Check if it's a trial (short duration)
                    if not source:
                        try:
                            created = datetime.fromisoformat(license_data.get('created_date', ''))
                            expiry = datetime.fromisoformat(license_data.get('expiry_date', ''))
                            days = (expiry - created).days
                            if days <= 7:
                                source = Platform.TRIAL.value
                        except:
                            pass
                    
                    # Default to gumroad for existing licenses (our primary platform)
                    if not source:
                        source = Platform.GUMROAD.value
                    
                    # Update license
                    license_data['platform'] = source
                    
                    # Try to set platform_transaction_id from existing data
                    if source == Platform.GUMROAD.value:
                        # Check for sale_id in various locations
                        sale_id = license_data.get('sale_id')
                        if not sale_id:
                            purchase_info = license_data.get('purchase_info', {})
                            sale_id = purchase_info.get('sale_id')
                        if sale_id:
                            license_data['platform_transaction_id'] = sale_id
                    
                    stats['migrated'] += 1
                    
                except Exception as e:
                    logger.error(f"Error migrating license {license_key}: {e}")
                    stats['errors'] += 1
            
            # Save updated licenses
            if stats['migrated'] > 0:
                if self.save_licenses(licenses):
                    logger.info(f"Platform migration complete: {stats}")
                else:
                    logger.error("Failed to save migrated licenses")
                    stats['errors'] += stats['migrated']
                    stats['migrated'] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Platform migration failed: {e}")
            return {'migrated': 0, 'already_migrated': 0, 'errors': 1}
    
    def handle_refund(self, license_key, refund_reason="customer_request"):
        """Handle license refund - deactivate the license
        
        Args:
            license_key: License key to refund
            refund_reason: Reason for refund (customer_request, dispute, fraud, etc)
        
        Returns:
            dict: Success/failure status
        """
        try:
            licenses = self.load_licenses()
            
            if license_key not in licenses:
                return {'success': False, 'error': 'invalid_license'}
            
            license_data = licenses[license_key]
            
            # Deactivate license
            license_data['is_active'] = False
            
            licenses[license_key] = license_data
            
            if self.save_licenses(licenses):
                logger.info(f"Refunded license {license_key} - Reason: {refund_reason}")
                
                # Log refund to audit trail
                self.log_refund(license_key, refund_reason)
                
                return {
                    'success': True,
                    'message': f'License {license_key} has been refunded and deactivated'
                }
            else:
                return {'success': False, 'error': 'failed_to_save'}
                
        except Exception as e:
            logger.error(f"Refund error: {e}")
            return {'success': False, 'error': 'refund_failed'}
    
    def log_refund(self, license_key, refund_reason):
        """Log refund to audit trail"""
        try:
            refund_record = {
                'timestamp': datetime.now().isoformat(),
                'event': 'refund',
                'license_key': license_key,
                'refund_reason': refund_reason
            }
            
            with open(self.purchases_file, 'a') as f:
                f.write(json.dumps(refund_record) + '\n')
            
            logger.info(f"Refund logged for license {license_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to log refund: {e}")
            return False
    
    def _get_refund_info_from_audit(self, license_key):
        """Get refund info from audit log"""
        try:
            with open(self.purchases_file, 'r') as f:
                for line in f:
                    record = json.loads(line)
                    if record.get('license_key') == license_key and record.get('event') == 'refund':
                        return {'timestamp': record.get('timestamp'), 'refund_reason': record.get('refund_reason')}
            return None
        except:
            return None
    
    def get_refund_status(self, license_key):
        """Check if a license has been refunded
        
        Returns:
            dict: License data with refund status
        """
        try:
            licenses = self.load_licenses()
            
            if license_key not in licenses:
                return {'success': False, 'error': 'invalid_license'}
            
            license_data = licenses[license_key]
            
            # Get refund info from audit log if refunded
            refund_info = None
            if not license_data.get('is_active'):
                refund_info = self._get_refund_info_from_audit(license_key)
            
            return {
                'success': True,
                'license_key': license_key,
                'is_active': license_data.get('is_active'),
                'is_refunded': not license_data.get('is_active', True),
                'refund_date': refund_info.get('timestamp') if refund_info else None,
                'refund_reason': refund_info.get('refund_reason') if refund_info else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get refund status: {e}")
            return {'success': False, 'error': 'lookup_failed'}
    
    def get_license_info(self, license_key):
        """Get complete license information (for support/admin)
        
        Returns:
            dict: Complete license and purchase data
        """
        try:
            licenses = self.load_licenses()
            
            if license_key not in licenses:
                return {'success': False, 'error': 'invalid_license'}
            
            license_data = licenses[license_key]
            
            # Read purchase info from audit log
            purchase_data = None
            try:
                with open(self.purchases_file, 'r') as f:
                    for line in f:
                        record = json.loads(line)
                        if record.get('license_key') == license_key and record.get('event') != 'refund':
                            purchase_data = record
                            break
            except:
                pass
            
            return {
                'success': True,
                'license': license_data,
                'purchase': purchase_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get license info: {e}")
            return {'success': False, 'error': 'lookup_failed'}    
    def convert_trial_to_full(self, email, new_license_key, purchase_info):
        """
        Convert trial license to full license (industry standard flow)
        
        Best Practice Flow:
        1. Find existing trial in trials.json
        2. Archive trial data (keep for analytics/audit)
        3. Create full license with trial history
        4. Mark trial as converted (don't delete - audit trail)
        
        Args:
            email: User's email address
            new_license_key: New full license key from purchase
            purchase_info: Dictionary with purchase details (product, price, date, etc.)
        
        Returns:
            Full license dictionary
        """
        try:
            trials = self.load_trials()
            licenses = self.load_licenses()
            
            # Find trial license by email in trials.json
            trial_key = None
            trial_data = None
            for t_key, t_data in trials.items():
                if t_data.get('email', '').lower() == email.lower():
                    trial_key = t_key
                    trial_data = t_data
                    break
            
            if trial_data:
                # Calculate trial usage stats
                trial_start = datetime.fromisoformat(trial_data.get('created_date'))
                trial_duration_days = (datetime.now() - trial_start).days
                
                # Mark trial as converted (keep for audit trail)
                trial_data['converted_to_full'] = True
                trial_data['conversion_date'] = datetime.now().isoformat()
                trial_data['full_license_key'] = new_license_key
                trial_data['is_active'] = False  # Deactivate trial
                trial_data['trial_duration_days'] = trial_duration_days
                
                # Update trial in trials.json
                trials[trial_key] = trial_data
                self.save_trials(trials)
                
                logger.info(
                    f"✅ Trial converted to full license\n"
                    f"   Email: {email}\n"
                    f"   Trial duration: {trial_duration_days} days\n"
                    f"   New license: {new_license_key[:8]}..."
                )
            else:
                logger.info(f"ℹ️  No trial found for {email} (new customer)")
            
            # Create full license with trial history
            expiry_date = datetime.now() + timedelta(days=purchase_info.get('expires_days', 36500))
            
            # Determine platform from purchase_info
            platform = purchase_info.get('source', Platform.GUMROAD.value)
            platform_id_field = get_platform_sale_id_field(platform)
            platform_transaction_id = purchase_info.get(platform_id_field)
            
            full_license = {
                'email': email,
                'created_date': datetime.now().isoformat(),
                'expiry_date': expiry_date.isoformat(),
                'is_active': True,
                'hardware_id': trial_data.get('hardware_id') if trial_data else None,
                'device_name': trial_data.get('device_name') if trial_data else None,
                'last_validation': datetime.now().isoformat(),
                'validation_count': 0,
                'source_license_key': purchase_info.get('source_license_key'),
                # Platform tracking
                'platform': platform,
                'platform_transaction_id': platform_transaction_id,
                # Trial conversion tracking
                'was_trial': trial_data is not None,
                'trial_started': trial_data.get('created_date') if trial_data else None,
                'trial_duration_days': trial_data.get('trial_duration_days', 0) if trial_data else 0
            }
            
            # Save full license to licenses.json
            licenses[new_license_key] = full_license
            self.save_licenses(licenses)
            
            logger.info(f"✅ Full license created: {new_license_key[:8]}... for {email}")
            
            return full_license
            
        except Exception as e:
            logger.error(f"❌ Failed to convert trial to full: {e}")
            return None
    
    def _deactivate_trial_for_email(self, email):
        """
        Deactivate trial when full license is activated
        
        Keeps trial record for audit trail but marks as superseded
        """
        try:
            licenses = self.load_licenses()
            email_lower = email.lower()
            
            for license_key, license_data in licenses.items():
                if license_data.get('email', '').lower() == email_lower and self.is_trial_license(license_key):
                    if license_data.get('is_active'):
                        license_data['is_active'] = False
                        license_data['deactivated_at'] = datetime.now().isoformat()
                        license_data['deactivation_reason'] = 'superseded_by_full'
                        
                        licenses[license_key] = license_data
                        self.save_licenses(licenses)
                        
                        logger.info(f"✅ Trial deactivated for {email} (superseded by full license)")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to deactivate trial: {e}")
            return False

    def find_license_by_email(self, email):
        """Find and return a license key for a given email
        
        Args:
            email: Customer email address
        
        Returns:
            dict: {'success': bool, 'license_key': str, 'error': str, 'message': str}
        """
        try:
            if not email or '@' not in email:
                return {
                    'success': False,
                    'error': 'invalid_email',
                    'message': 'Please provide a valid email address'
                }
            
            licenses = self.load_licenses()
            email_lower = email.lower().strip()
            
            # Search for licenses matching this email
            found_licenses = []
            for license_key, license_data in licenses.items():
                if license_data.get('email', '').lower() == email_lower:
                    found_licenses.append({
                        'license_key': license_key,
                        'is_active': license_data.get('is_active', False),
                        'created_date': license_data.get('created_date'),
                        'expiry_date': license_data.get('expiry_date'),
                        'device_name': license_data.get('device_name')
                    })
            
            if not found_licenses:
                return {
                    'success': False,
                    'error': 'no_license_found',
                    'message': 'No license found for this email address'
                }
            
            # Return the most recent active license, or if none active, the most recent one
            active_licenses = [lic for lic in found_licenses if lic['is_active']]
            target_license = active_licenses[0] if active_licenses else found_licenses[0]
            
            logger.info(f"Found license {target_license['license_key']} for email {email}")
            
            return {
                'success': True,
                'license_key': target_license['license_key'],
                'is_active': target_license['is_active'],
                'expiry_date': target_license['expiry_date'],
                'message': 'License found successfully'
            }
            
        except Exception as e:
            logger.error(f"Error finding license by email: {e}")
            return {
                'success': False,
                'error': 'lookup_failed',
                'message': 'Failed to lookup license'
            }