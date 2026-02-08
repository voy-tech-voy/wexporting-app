# Webhook Verification Strategy

## The Reality Check

You're right to question this! **I am NOT 100% sure** the refund webhook will work without testing because:

1. ❌ I don't know what fields Gumroad actually sends
2. ❌ I don't know if they send a separate refund webhook
3. ❌ I don't know the exact parameter names
4. ❌ I don't have access to Gumroad's current API docs

---

## How to Verify (Step by Step)

### **Phase 1: Understanding Gumroad's Behavior** (5 minutes)

**Check Gumroad's Documentation:**
1. Go to: https://gumroad.com/creator/install/webhooks
2. Look for:
   - ✓ What events are available?
   - ✓ Is there a "refund" event?
   - ✓ What fields does it include?
   - ✓ Or is refund a flag in the sale webhook?

**What you're looking for:**
```
Option A: Separate refund webhook
POST /api/v1/webhooks/gumroad/refund
→ Fields: license_key, sale_id, refund_reason

Option B: Flag in purchase webhook
POST /api/v1/webhooks/gumroad
→ Fields: license_key, refunded: true

Option C: Different endpoint/fields entirely
→ Whatever Gumroad actually uses
```

### **Phase 2: Test with Diagnostic Endpoints** (5 minutes)

**After deploying to PythonAnywhere:**

1. **Check if test endpoint works:**
   ```bash
   curl https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad/test-refund \
     -d "license_key=TEST" \
     -d "refunded=true"
   ```

2. **View what was logged:**
   ```bash
   curl https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad/webhook-logs
   ```

3. **Or use the testing script:**
   ```bash
   python test_webhook_scenarios.py
   ```

### **Phase 3: Test with Real Gumroad Data** (Varies)

**Option A: Use Gumroad's Test Webhook (Best)**
1. Go to Gumroad product settings
2. Find webhook configuration section
3. Click "Send Test Webhook" or "Resend Webhook"
4. Select "refund" event if available
5. Monitor logs to see what actually arrives

**Option B: Real Purchase + Refund (Costs Money)**
1. Make small test purchase
2. Immediately issue refund
3. Monitor logs to see webhook data
4. Check if it matches our expectations

**Option C: Ask Gumroad Support**
- Email Gumroad support
- Ask: "What exact fields do you send in refund webhooks?"
- They can tell you directly

---

## What We're Testing For

| Question | Impact | How to Check |
|----------|--------|--------------|
| **Does Gumroad send separate refund webhook?** | Critical | Check docs or test webhook logs |
| **What field contains the license key?** | Critical | Monitor `webhook-logs` endpoint |
| **What field indicates it's a refund?** | Critical | Monitor `webhook-logs` endpoint |
| **Are there required auth headers?** | High | Check request headers in logs |
| **What is the exact endpoint they POST to?** | High | Verify against our `/gumroad/refund` URL |

---

## Current Implementation Status

### ✅ What We Built
- Refund webhook endpoint: `/api/v1/webhooks/gumroad/refund`
- Diagnostic logging: `webhook_debug.jsonl`
- Debug viewer: `/api/v1/webhooks/gumroad/webhook-logs`
- Test scenarios: `test_webhook_scenarios.py`
- License refund methods: `handle_refund()`, `get_refund_status()`

### ⚠️ What Might Need Adjustment
- **Field names** - If Gumroad uses different names
- **Webhook endpoint** - If they POST elsewhere
- **Event structure** - If refund is a flag, not separate event
- **Authentication** - If special headers are needed

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Wrong field names | 40% | Refund webhook ignored | Test first, easy to fix |
| Wrong webhook endpoint | 20% | Webhook not received | Gumroad docs should clarify |
| Refund as flag, not event | 30% | Need to handle in purchase webhook | Can add logic to handle both |
| Missing auth headers | 10% | Webhook rejected | Check request headers |
| Gumroad API changed | 5% | Incompatible | Monitor, update as needed |

---

## Testing Checklist

Before going live:

- [ ] **Read Gumroad docs** - What do they actually send?
- [ ] **Test diagnostic endpoint** - Can we capture data?
- [ ] **Send test webhook** - Does Gumroad have test feature?
- [ ] **Monitor logs** - What fields are actually there?
- [ ] **Compare to code** - Do field names match?
- [ ] **Adjust if needed** - Update field names/logic if different
- [ ] **Test real refund** - Make small purchase, test refund flow
- [ ] **Verify deactivation** - Does license actually deactivate?
- [ ] **Test in app** - Does customer's app detect deactivated license?

---

## Quick Decision Tree

```
Does Gumroad docs mention refund webhooks?
├─ YES → What fields do they send?
│   ├─ license_key, sale_id, refund_reason → Use our endpoint (likely works)
│   └─ Different fields → Update field mappings
│
└─ NO → Check if it's a flag in purchase webhook
    ├─ YES → Update purchase webhook handler
    └─ NO → Contact Gumroad support for clarification
```

---

## If Something Goes Wrong

**Scenario: Refund webhook not working**

1. Check logs:
   ```bash
   curl https://wavyvoy.pythonanywhere.com/api/v1/webhooks/gumroad/webhook-logs
   ```

2. Is webhook being received?
   - YES → Fields don't match, update code
   - NO → Gumroad not sending to this endpoint, check Gumroad settings

3. Are field names different?
   ```python
   # In webhooks.py, update this line:
   gumroad_license_key = data.get('actual_field_name')
   ```

4. Is it a flag in purchase webhook?
   ```python
   # In gumroad_webhook() purchase handler, add:
   if data.get('refunded') == 'true':
       manager.handle_refund(license_key, 'gumroad_refund')
   ```

---

## Summary

**My honest assessment:**

- ✅ **The refund deactivation logic is solid** (tested and working)
- ✅ **The webhook endpoint is ready** (catches everything Gumroad sends)
- ❌ **The field names might be wrong** (until we see real Gumroad data)

**So:**
1. Deploy the endpoint
2. Test with diagnostic tools
3. See what Gumroad actually sends
4. Adjust field names if needed (1 minute change)
5. Deploy confident fix

**Total time to verify: 10-20 minutes**

---

## Next Steps

1. **Check Gumroad docs** for webhook structure
2. **Deploy to PythonAnywhere** 
3. **Run diagnostic tests** to see real data
4. **Adjust code if needed** based on actual data
5. **Test end-to-end** with real refund

Want me to help with any of these steps?
