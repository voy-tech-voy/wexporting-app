# Deployment Checklist ✅

## Pre-Deployment Verification

- [x] Refactored LicenseManager for lean storage
- [x] Added log_purchase() method for audit trail
- [x] Created purchases.jsonl with proper structure
- [x] Webhooks.py integrated (no changes needed)
- [x] Test suite created and passing
- [x] Helper utilities created for querying
- [x] Documentation complete

## Deployment Steps (PythonAnywhere)

### Step 1: Reload Web App
```
CRITICAL: Old code is cached. This MUST be done first.

1. Go to https://www.pythonanywhere.com
2. Login to your account
3. Click "Web" tab
4. Find "ImgApp" or your app name
5. Click green "Reload" button (top right)
6. Wait for status to show green "Reload date: now"
```

**Why this matters:** Python caches imported modules. Reloading forces a fresh import of the refactored license_manager.py

### Step 2: Verify Files on Server

```bash
# SSH into PythonAnywhere
ssh yourname@ssh.pythonanywhere.com

# Check that files exist
ls -la /home/yourname/ImgApp/server/data/

# Should show:
# licenses.json (your existing licenses)
# purchases.jsonl (created by first test)
# licenses_backup.json (safety backup)
```

### Step 3: Test with Gumroad

#### Option A: Make Real Purchase
1. Go to your Gumroad product page: https://gumroad.com/...
2. Click "Buy Now"
3. Complete purchase with test card (if available)
4. Should receive license email within seconds

#### Option B: Ask Gumroad to Resend Webhook
1. Go to Gumroad dashboard
2. Find recent sale
3. Click "Resend webhook" or similar option
4. Check webhook response for license key

#### Option C: Manual Test (if webhook URL not working)
```bash
# On PythonAnywhere, test the endpoint manually
curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad \
  -d "email=test@example.com" \
  -d "full_name=Test User" \
  -d "product_name=Test Product" \
  -d "price=100" \
  -d "currency=usd" \
  -d "sale_id=test123" \
  -d "license_key=TEST-ABC123" \
  -d "purchaser_id=999"
```

### Step 4: Verify Output

#### Check licenses.json
```bash
# View latest license entry
tail -50 /home/yourname/ImgApp/server/data/licenses.json

# Should show LEAN structure with 11 fields:
# - email, customer_name, created_date, expiry_date
# - is_active, hardware_id, device_name
# - last_validation, validation_count
# - purchase_source, purchase_id

# NOT should show: full Gumroad data, product details, etc.
```

#### Check purchases.jsonl
```bash
# View latest purchase record
tail -1 /home/yourname/ImgApp/server/data/purchases.jsonl | python -m json.tool

# Should show FULL audit with 15+ fields:
# - timestamp, license_key, source, sale_id
# - customer_id, product_name, tier, price
# - is_recurring, is_refunded, is_disputed, etc.
```

#### Check Email
1. Check Gmail inbox (methos014@gmail.com or configured address)
2. Should have received "Your ImageWave License" email
3. Email should contain license key in format: IW-XXXXXX-XXXXXXXX

### Step 5: Run Analysis Script

```bash
# On local machine or PythonAnywhere
python purchase_audit_helper.py

# Should output:
# ✓ Total Purchases: (count)
# ✓ Total Revenue: $(amount)
# ✓ By Source: gumroad: (count)
# ✓ Top Products: (product names)
```

---

## Post-Deployment Monitoring

### Daily Checks
```python
# Check for new purchases
from purchase_audit_helper import PurchaseAuditLog
audit = PurchaseAuditLog()
stats = audit.get_purchase_stats()

print(f"Purchases today: {stats['total_purchases']}")
print(f"Revenue today: ${stats['total_revenue']}")
```

### Weekly Review
```bash
# Export purchase history
python purchase_audit_helper.py | grep -A 20 "Recent Gumroad"

# Verify no errors
tail -100 server/logs/error.log | grep -i purchase
```

### Monthly Reporting
```bash
# Export for accounting
python -c "
from purchase_audit_helper import PurchaseAuditLog
audit = PurchaseAuditLog()
audit.export_to_csv('purchases_2025-12.csv')
print('✓ Exported to CSV for accounting')
"
```

---

## Rollback Plan (If Issues Arise)

### If Something Goes Wrong

```bash
# Step 1: Check the error
tail -50 /home/yourname/ImgApp/server/logs/error.log

# Step 2: Restore old code (if available)
cp /home/yourname/ImgApp/server/services/license_manager.py.bak \
   /home/yourname/ImgApp/server/services/license_manager.py

# Step 3: Reload again
# Go to Web tab, click Reload

# Step 4: Restore licenses if needed
cp /home/yourname/ImgApp/server/data/licenses_backup.json \
   /home/yourname/ImgApp/server/data/licenses.json
```

### If License File is Corrupted

```bash
# All old licenses are backed up here:
# - server/data/licenses_backup.json
# - server/data/licenses_backup1.json
# - config/licenses.json (old location)

# Restore from backup
cp /home/yourname/ImgApp/server/data/licenses_backup.json \
   /home/yourname/ImgApp/server/data/licenses.json
```

---

## Troubleshooting

### Problem: "No webhook received"
**Cause:** PythonAnywhere reload not completed  
**Solution:** 
1. Go to Web tab
2. Wait for reload to complete (check status = green)
3. Resend webhook from Gumroad

### Problem: "purchases.jsonl not created"
**Cause:** log_purchase() method not called  
**Solution:**
1. Check server logs for errors
2. Verify purchase_info is being passed to create_license()
3. Check file permissions on server/data/ directory

### Problem: "License file corruption"
**Cause:** Interrupted write operation  
**Solution:**
1. Restore from backup: `cp licenses_backup.json licenses.json`
2. Verify integrity: `python -c "import json; json.load(open('licenses.json'))"`

### Problem: "Old code still running"
**Cause:** Python cache not cleared  
**Solution:**
1. Go to Web tab
2. Click "Reload" button
3. Wait for green status
4. Try webhook again

---

## Validation Checklist

After deployment, verify:

- [ ] PythonAnywhere Web App reloaded (shows "Reload date: now")
- [ ] Test Gumroad purchase received license email
- [ ] licenses.json contains new license with 11 fields
- [ ] purchases.jsonl created with audit record
- [ ] License key format is IW-XXXXXX-XXXXXXXX
- [ ] purchase_source shows "gumroad"
- [ ] purchase_id matches Gumroad sale_id
- [ ] Email was sent successfully
- [ ] purchase_audit_helper.py runs without errors
- [ ] Stats show correct purchase count and revenue

---

## Success Criteria

✅ Deployment is successful when:

1. **License emails are being sent** after Gumroad purchases
2. **licenses.json is lean** with only 11 fields per license
3. **purchases.jsonl is populated** with full audit trail
4. **No errors in logs** related to license creation
5. **purchase_audit_helper.py works** and shows correct stats
6. **Old licenses still work** (hardware binding, expiry check)

---

## After Successful Deployment

### Document the Changes
```bash
# Create a changelog entry
echo "
[2025-12-14] License Storage Optimization
- Refactored license storage to separate validation (lean) from audit trail
- licenses.json: 11 fields (fast validation)
- purchases.jsonl: 15+ fields (complete audit trail)
- Test passed: All licenses correctly created with new structure
- Deployment: Ready for PythonAnywhere reload
" >> CHANGELOG.md
```

### Clean Up Test Files
```bash
# After confirming everything works, clean up:
# (Keep test files as documentation)
# - test_lean_storage.py → Keep for future regression testing
# - purchase_audit_helper.py → Keep for regular audits
# - test_webhook_logs.jsonl → Can delete
```

### Set Up Monitoring
```python
# In your monitoring system, add:
# 1. Check that purchases.jsonl is being written to
# 2. Alert if webhook returns error status
# 3. Monitor email delivery rate
# 4. Track license validation success rate
```

---

## Quick Reference

### File Locations
- **Code**: `server/services/license_manager.py`
- **Webhook**: `server/api/webhooks.py`
- **Licenses**: `server/data/licenses.json`
- **Audit Log**: `server/data/purchases.jsonl`
- **Tests**: `test_lean_storage.py`
- **Helpers**: `purchase_audit_helper.py`

### Key Methods
```python
# Create license with purchase tracking
license_key = manager.create_license(
    email=email,
    customer_name=name,
    expires_days=36500,
    purchase_info=purchase_info  # Includes source, sale_id, etc.
)

# Query purchases
audit = PurchaseAuditLog()
refunded = audit.get_refunded_purchases()
gumroad = audit.get_purchases_by_source('gumroad')
stats = audit.get_purchase_stats()
```

### Common Checks
```bash
# Is the app running?
curl https://wavyvoy.pythonanywhere.com/

# Does the webhook work?
curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad -d "email=test@test.com"

# How many licenses?
cat server/data/licenses.json | python -c "import json,sys; print(len(json.load(sys.stdin)))"

# How many purchases?
wc -l server/data/purchases.jsonl
```

---

**Ready to Deploy!** 🚀

Follow these steps and your license system will be optimized for production.
