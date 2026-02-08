# Multi-Platform Support Implementation Summary

## Overview

This implementation adds comprehensive multi-platform support for both **Gumroad** and **Microsoft Store** distribution channels. The architecture is designed to be:

- **Platform-agnostic**: Same license validation logic for all platforms
- **Extensible**: Easy to add future platforms (Stripe, etc.)
- **Backward-compatible**: Existing Gumroad licenses continue to work

---

## Phase 1: Data Model Enhancement ✅

### Changes to `server/services/license_manager.py`

1. **Added Platform Enum**:
   ```python
   class Platform(str, Enum):
       GUMROAD = "gumroad"
       MSSTORE = "msstore"
       STRIPE = "stripe"
       DIRECT = "direct"
       TRIAL = "trial"
   ```

2. **New Helper Function**:
   - `get_platform_sale_id_field(platform)` - Maps platform to its transaction ID field name

3. **Updated `create_license()`**:
   - Added `platform` parameter
   - Auto-detects platform from `purchase_info.source` if not provided
   - Stores `platform` and `platform_transaction_id` fields

4. **New Platform-Agnostic Methods**:
   - `find_license_by_platform_id(platform, transaction_id)` - Find license by any platform's ID
   - `find_licenses_by_platform(platform)` - Get all licenses for a platform
   - `deactivate_by_platform_id(platform, transaction_id, reason)` - Deactivate by platform ID

5. **Migration Function**:
   - `migrate_existing_licenses_platform()` - One-time migration for existing licenses

---

## Phase 2: MS Store Webhook Handler ✅

### Changes to `server/api/webhooks.py`

1. **New Imports**:
   - `from services.license_manager import Platform, get_platform_sale_id_field`

2. **MS Store Product Mapping**:
   ```python
   MSSTORE_PRODUCT_DURATIONS = {
       "imgapp_lifetime": 36500,
       "imgapp_yearly": 365,
       "imgapp_monthly": 30,
   }
   ```

3. **New Functions**:
   - `verify_msstore_webhook()` - Verify Azure AD JWT or shared secret
   - `normalize_msstore_purchase()` - Convert MS Store webhook to standard format

4. **New Endpoints**:
   - `POST /webhooks/msstore` - Main MS Store webhook handler
   - `POST /webhooks/msstore/test` - Dev-only test endpoint

5. **Helper Functions**:
   - `_handle_msstore_purchase()` - Process new purchases
   - `_handle_msstore_refund()` - Process refunds
   - `_handle_msstore_cancellation()` - Process subscription cancellations

---

## Phase 3: Config & Environment ✅

### Changes to `server/config/settings.py`

Added MS Store configuration:
```python
# Azure AD app registration
MSSTORE_TENANT_ID = os.environ.get('MSSTORE_TENANT_ID')
MSSTORE_CLIENT_ID = os.environ.get('MSSTORE_CLIENT_ID')
MSSTORE_CLIENT_SECRET = os.environ.get('MSSTORE_CLIENT_SECRET')

# Store identifiers
MSSTORE_STORE_ID = os.environ.get('MSSTORE_STORE_ID')
MSSTORE_APP_ID = os.environ.get('MSSTORE_APP_ID')

# Webhook verification
VERIFY_MSSTORE_WEBHOOK = os.environ.get('VERIFY_MSSTORE_WEBHOOK', 'true').lower() == 'true'
```

### Changes to `wbf_pythonanywhere_com_wsgi.py`

Added Section 7 for MS Store configuration with environment variable templates.

---

## Phase 4: Client Platform Detection ✅

### New File: `client/utils/platform_detection.py`

1. **Platform Detection**:
   - `is_msstore_app()` - Detects if running as MSIX package
   - `get_app_platform()` - Returns current platform
   - `get_cached_platform()` - Cached version (run once)

2. **Helper Functions**:
   - `get_platform_display_name()` - UI-friendly platform name
   - `get_platform_purchase_url()` - Platform-specific purchase URL
   - `should_show_gumroad_ui()` - UI visibility logic
   - `should_use_store_license()` - License check mode

3. **MS Store License Checker**:
   - `MSStoreLicenseChecker` class
   - Uses Windows.Services.Store APIs
   - Async license validation

### Changes to `client/gui/login_window.py`

1. **Platform Awareness**:
   - Detects platform on init
   - Shows platform indicator for MS Store users
   - Different trial flow for MS Store apps

2. **New Methods**:
   - `_try_msstore_silent_auth()` - Silent authentication for Store apps
   - `_save_msstore_session()` - Save Store license session
   - `_try_msstore_trial()` - MS Store trial activation
   - `_show_gumroad_trial_dialog()` - Standard trial dialog

---

## Phase 5: Testing & Migration ✅

### New Admin Endpoints in `server/api/routes.py`

1. **`POST /admin/migrate-platforms`**
   - One-time migration for existing licenses
   - Adds `platform` field to all licenses
   - Safe to run multiple times

2. **`GET /admin/platform-stats`**
   - Returns license counts by platform
   - Shows migration status

3. **`GET /admin/find-by-platform?platform={name}`**
   - List all licenses from specific platform
   - Sanitized output for admin review

### Updated `API_ENDPOINTS_REFERENCE.md`

Added documentation for:
- MS Store webhook endpoints
- Admin platform management endpoints
- Example requests/responses

---

## Deployment Checklist

### PythonAnywhere Server

1. **Update Code**: Pull latest changes

2. **Run Migration**:
   ```bash
   curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/admin/migrate-platforms \
     -H "X-Admin-Key: YOUR_ADMIN_KEY"
   ```

3. **Verify Migration**:
   ```bash
   curl -X GET https://wavyvoy.pythonanywhere.com/api/v1/admin/platform-stats \
     -H "X-Admin-Key: YOUR_ADMIN_KEY"
   ```

4. **Set MS Store Env Vars** (when ready):
   - `MSSTORE_TENANT_ID`
   - `MSSTORE_CLIENT_ID`
   - `MSSTORE_CLIENT_SECRET`
   - `VERIFY_MSSTORE_WEBHOOK=true`

### Microsoft Store Setup (Future)

1. Register app in Azure AD
2. Configure Partner Center webhook
3. Set webhook URL: `https://wavyvoy.pythonanywhere.com/api/v1/webhooks/msstore`
4. Update `MSSTORE_*` environment variables
5. Map product SKUs in `MSSTORE_PRODUCT_DURATIONS`

---

## Files Modified

| File | Changes |
|------|---------|
| `server/services/license_manager.py` | Platform enum, new methods, migration |
| `server/api/webhooks.py` | MS Store webhook handler |
| `server/api/routes.py` | Admin migration endpoints |
| `server/config/settings.py` | MS Store config vars |
| `wbf_pythonanywhere_com_wsgi.py` | MS Store env var templates |
| `client/utils/platform_detection.py` | NEW - Platform detection |
| `client/gui/login_window.py` | Platform-aware UI |
| `API_ENDPOINTS_REFERENCE.md` | New endpoint docs |

---

## Testing Commands

### Test License Manager Import
```bash
cd server
python -c "from services.license_manager import Platform; print(Platform.all_values())"
```

### Test Webhooks Import
```bash
cd server
python -c "from api.webhooks import msstore_webhook; print('OK')"
```

### Simulate MS Store Webhook (Dev)
```bash
curl -X POST http://localhost:5000/api/v1/webhooks/msstore/test \
  -H "Content-Type: application/json" \
  -d '{
    "orderId": "test-order-123",
    "orderStatus": "Completed",
    "productId": "imgapp_lifetime",
    "purchaser": {"email": "test@example.com"},
    "purchasedAt": "2024-01-01T00:00:00Z"
  }'
```
