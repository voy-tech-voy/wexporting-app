# Gumroad Webhook Testing Guide

## Before We Go Live

Before deploying the refund webhook to production, we need to **verify what Gumroad actually sends**.

---

## Testing Endpoints Available

### 1. **Test Webhook Endpoint** (NEW)
```
POST /api/v1/webhooks/gumroad/test-refund
```
- Logs ALL webhook data received
- Perfect for debugging
- Shows exact field names and values

**Response shows:**
```json
{
  "status": "debug_logged",
  "message": "Webhook data logged to webhook_debug.jsonl",
  "received_fields": ["license_key", "sale_id", "refunded", ...],
  "data_sample": {...}
}
```

### 2. **View All Webhook Logs** (NEW)
```
GET /api/v1/webhooks/gumroad/webhook-logs
```
- Shows last 50 webhooks received
- Full diagnostic data
- Includes headers and content-type

### 3. **View Purchase Webhooks Only**
```
GET /api/v1/webhooks/gumroad/debug
```
- Shows last 20 purchase webhooks
- Good for comparing purchase vs refund data

---

## How to Test

### **Option 1: Use Gumroad's Webhook Testing UI** (Easiest)

1. Go to Gumroad Dashboard
2. Product → Webhooks/Settings
3. Look for "Test Webhook" or "Resend Webhook" button
4. Send a test event
5. Check if it's logged:
   ```bash
   curl https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad/webhook-logs
   ```

### **Option 2: Test with Real Purchase + Refund**

1. Make a test purchase on your product
2. Get refunded (via Gumroad dashboard)
3. Monitor logs:
   ```bash
   # In terminal, keep checking for new webhooks
   curl https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad/webhook-logs | python -m json.tool | tail -50
   ```

### **Option 3: Manual Webhook Testing (Local)**

If you have access to your webhook URL, you can test manually:

```bash
# Test what Gumroad MIGHT send for refund
curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad/test-refund \
  -d "license_key=TEST-LICENSE-KEY" \
  -d "sale_id=TEST-SALE-ID" \
  -d "refunded=true"
```

Then check:
```bash
curl https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad/webhook-logs
```

---

## What to Look For

### **Scenario 1: Separate Refund Webhook**
```json
{
  "resource_type": "sale",
  "action": "refunded",
  "id": "SALE-ID",
  "license_key": "GUMROAD-LICENSE-KEY"
}
```

→ **What to do:** Refund endpoint might work as-is

### **Scenario 2: Refund Flag in Purchase Webhook**
```json
{
  "id": "SALE-ID",
  "email": "customer@example.com",
  "license_key": "GUMROAD-LICENSE-KEY",
  "refunded": "true"
}
```

→ **What to do:** Update purchase webhook to handle refunds

### **Scenario 3: Different Field Names**
```json
{
  "transaction_id": "...",
  "gumroad_license_key": "...",
  "refund_timestamp": "..."
}
```

→ **What to do:** Map actual field names in our code

---

## After Testing: Adjust Code If Needed

Once you know what Gumroad sends, we might need to update:

### **Update 1: Match Field Names**
```python
# In webhooks.py - gumroad_refund_webhook()
gumroad_license_key = data.get('license_key')  # Might need to be different name
```

### **Update 2: Handle Refund Flag**
If Gumroad sends `refunded: true` in purchase webhook instead:
```python
# In webhooks.py - gumroad_webhook()
if data.get('refunded') == 'true':
    # Process refund instead of creating new license
    license_manager.handle_refund(existing_license_key, 'gumroad_refund')
```

### **Update 3: Add New Webhook Endpoint**
If Gumroad sends data to different endpoint:
```python
@webhook_bp.route('/gumroad/sale-refunded', methods=['POST'])
def gumroad_sale_refunded():
    # Handle whatever endpoint Gumroad actually uses
    ...
```

---

## Debugging Checklist

- [ ] Can you access the test endpoint?
- [ ] Does Gumroad have webhook documentation?
- [ ] Can you see test webhooks in the logs?
- [ ] Are field names what we expected?
- [ ] Do parameter names match our code?
- [ ] Does Gumroad send refund as separate event or flag?
- [ ] What is the exact webhook payload structure?
- [ ] Are there any authentication headers we need?

---

## Quick Reference: What We'll Check

```
Gumroad sends refund webhook
        ↓
Webhook lands at /api/v1/webhooks/gumroad/test-refund
        ↓
Logged to webhook_debug.jsonl with full diagnostic data
        ↓
View via /api/v1/webhooks/gumroad/webhook-logs
        ↓
See EXACTLY what fields are present
        ↓
Compare to our expected field names
        ↓
Adjust code if needed
        ↓
Deploy with confidence ✅
```

---

## Current Assumptions (May Need Adjustment)

Our refund endpoint assumes Gumroad sends:
- `license_key` - The Gumroad license key
- `sale_id` - The sale/transaction ID
- `refund_reason` - Reason for refund (optional)

**These might be wrong!** We need to test to know for sure.

---

## Summary

1. **Use test endpoint** to capture real webhook data
2. **Check webhook logs** to see what Gumroad actually sends
3. **Compare field names** to what we're looking for
4. **Adjust code** if field names don't match
5. **Deploy** once verified

---

## Testing Status

- [ ] Test endpoint deployed (ready to use)
- [ ] Webhook logs available for review
- [ ] Real data captured from Gumroad
- [ ] Field names verified
- [ ] Code adjusted if needed
- [ ] Ready for production

**Next step:** Use the test endpoint to capture actual Gumroad webhook data!
