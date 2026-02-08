# Data Structure Reference

## licenses.json Format (LEAN - Validation Only)

Each license entry contains exactly **11 fields**:

```json
{
  "IW-728887-2061BB6E": {
    "email": "customer@example.com",
    "customer_name": "Customer Name",
    "created_date": "2025-12-14T17:14:47.364464",
    "expiry_date": "2135-12-14T17:14:47.364464",
    "is_active": true,
    "hardware_id": null,
    "device_name": null,
    "last_validation": null,
    "validation_count": 0,
    "purchase_source": "gumroad",
    "purchase_id": "YhDQXVee5s7VpKkO_W0lLQ=="
  }
}
```

### Field Definitions

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| **email** | string | Customer email (primary identifier) | `"user@example.com"` |
| **customer_name** | string | Display name | `"John Doe"` |
| **created_date** | ISO 8601 | License creation timestamp | `"2025-12-14T17:14:47.364464"` |
| **expiry_date** | ISO 8601 | License expiration datetime | `"2135-12-14T17:14:47.364464"` |
| **is_active** | boolean | License activation status | `true` or `false` |
| **hardware_id** | string \| null | Device hardware ID (first validation) | `"edf58327a9b5ca53"` |
| **device_name** | string \| null | Device name (first validation) | `"Windows-DESKTOP-ABC123"` |
| **last_validation** | ISO 8601 \| null | Last successful validation time | `"2025-12-14T19:30:22.123456"` |
| **validation_count** | integer | Total validation attempts | `42` |
| **purchase_source** | string | Payment platform identifier | `"gumroad"` `"stripe"` `"direct"` |
| **purchase_id** | string \| null | Platform transaction ID | `"YhDQXVee5s7VpKkO_W0lLQ=="` |

---

## purchases.jsonl Format (COMPLETE Audit Trail)

JSON Lines format - one purchase record per line (newline-delimited JSON):

```jsonl
{"timestamp": "2025-12-14T17:14:47.365465", "license_key": "IW-728887-2061BB6E", "source": "gumroad", "source_license_key": "54833B0C-1234567890ABCDEF", "sale_id": "YhDQXVee5s7VpKkO_W0lLQ==", "customer_id": "8553431068502", "product_id": "HutvZTz0eYm7TYkOfqTmEg==", "product_name": "ImageWave Converter", "tier": "Lifetime", "price": "500", "currency": "usd", "purchase_date": "2025-12-14T17:14:47.364464", "is_recurring": false, "recurrence": null, "subscription_id": null, "is_refunded": false, "is_disputed": false, "is_test": false}
```

### Field Definitions

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| **timestamp** | ISO 8601 | When record was logged | `"2025-12-14T17:14:47.365465"` |
| **license_key** | string | Generated license key (linkage) | `"IW-728887-2061BB6E"` |
| **source** | string | Payment platform | `"gumroad"` \| `"stripe"` \| `"direct"` |
| **source_license_key** | string | Platform's license key | `"54833B0C-1234567890ABCDEF"` |
| **sale_id** | string | Platform transaction ID (unique) | `"YhDQXVee5s7VpKkO_W0lLQ=="` |
| **customer_id** | string | Platform customer ID | `"8553431068502"` |
| **product_id** | string | Platform product ID | `"HutvZTz0eYm7TYkOfqTmEg=="` |
| **product_name** | string | Product display name | `"ImageWave Converter"` |
| **tier** | string | Subscription tier/type | `"Lifetime"` \| `"Monthly"` \| `"Yearly"` |
| **price** | string | Purchase amount | `"500"` |
| **currency** | string | Currency code (lowercase) | `"usd"` \| `"eur"` \| `"gbp"` |
| **purchase_date** | ISO 8601 | Original purchase timestamp | `"2025-12-14T17:14:47.364464"` |
| **is_recurring** | boolean | Subscription status | `true` \| `false` |
| **recurrence** | string \| null | Subscription frequency | `"monthly"` \| `"annual"` \| `null` |
| **subscription_id** | string \| null | For recurring charges | `"sub_123456"` \| `null` |
| **renewal_date** | ISO 8601 \| null | Next renewal date | `"2025-01-14T17:14:47..."` \| `null` |
| **is_refunded** | boolean | Refund status | `true` \| `false` |
| **refund_date** | ISO 8601 \| null | When refund occurred | `"2025-12-20T10:00:00..."` \| `null` |
| **is_disputed** | boolean | Dispute status | `true` \| `false` |
| **is_test** | boolean | Test transaction flag | `true` \| `false` |

---

## Example Data Flow

### Step 1: Gumroad Webhook Received
```json
{
  "email": "customer@example.com",
  "full_name": "John Doe",
  "product_name": "ImageWave Converter",
  "product_id": "HutvZTz0eYm7TYkOfqTmEg==",
  "price": "500",
  "currency": "usd",
  "sale_id": "YhDQXVee5s7VpKkO_W0lLQ==",
  "license_key": "54833B0C-1234567890ABCDEF",
  "purchaser_id": "8553431068502",
  "variants[Tier]": "",
  "refunded": "false",
  "disputed": "false",
  "test": "false"
}
```

### Step 2: Normalized by webhooks.py
```python
purchase_info = {
    'source': 'gumroad',
    'source_license_key': '54833B0C-1234567890ABCDEF',
    'sale_id': 'YhDQXVee5s7VpKkO_W0lLQ==',
    'customer_id': '8553431068502',
    'product_id': 'HutvZTz0eYm7TYkOfqTmEg==',
    'product_name': 'ImageWave Converter',
    'tier': 'Lifetime',  # Defaulted from empty
    'price': '500',
    'currency': 'usd',
    'purchase_date': '2025-12-14T17:14:47.364464',
    'is_recurring': False,
    'recurrence': None,
    'subscription_id': None,
    'is_refunded': False,
    'is_disputed': False,
    'is_test': False
}
```

### Step 3: License Created (licenses.json)
```json
{
  "email": "customer@example.com",
  "customer_name": "John Doe",
  "created_date": "2025-12-14T17:14:47.364464",
  "expiry_date": "2135-12-14T17:14:47.364464",
  "is_active": true,
  "hardware_id": null,
  "device_name": null,
  "last_validation": null,
  "validation_count": 0,
  "purchase_source": "gumroad",
  "purchase_id": "YhDQXVee5s7VpKkO_W0lLQ=="
}
```

### Step 4: Purchase Logged (purchases.jsonl)
```json
{
  "timestamp": "2025-12-14T17:14:47.365465",
  "license_key": "IW-728887-2061BB6E",
  "source": "gumroad",
  "source_license_key": "54833B0C-1234567890ABCDEF",
  "sale_id": "YhDQXVee5s7VpKkO_W0lLQ==",
  "customer_id": "8553431068502",
  "product_id": "HutvZTz0eYm7TYkOfqTmEg==",
  "product_name": "ImageWave Converter",
  "tier": "Lifetime",
  "price": "500",
  "currency": "usd",
  "purchase_date": "2025-12-14T17:14:47.364464",
  "is_recurring": false,
  "recurrence": null,
  "subscription_id": null,
  "is_refunded": false,
  "is_disputed": false,
  "is_test": false
}
```

---

## Size Comparison

### Before Optimization (Bloated)
```
Per License: ~1.2 KB (50+ fields including all Gumroad data)
For 1000 licenses: ~1.2 MB
```

### After Optimization (Lean)
```
licenses.json: ~300 bytes per license (11 fields)
purchases.jsonl: ~800 bytes per record (15+ fields)
For 1000 licenses: ~1.1 MB total (lean + audit)

Result: Same total size, but optimized structure!
```

---

## Reading the Files

### Python - Read licenses.json
```python
import json

with open('server/data/licenses.json', 'r') as f:
    licenses = json.load(f)

license_data = licenses['IW-728887-2061BB6E']
print(f"Email: {license_data['email']}")
print(f"Expires: {license_data['expiry_date']}")
```

### Python - Read purchases.jsonl
```python
import json

with open('server/data/purchases.jsonl', 'r') as f:
    for line in f:
        purchase = json.loads(line)
        print(f"{purchase['timestamp']}: {purchase['product_name']} - ${purchase['price']}")
```

### Command Line - View licenses
```bash
# Pretty print all licenses
cat server/data/licenses.json | python -m json.tool

# Pretty print one license
cat server/data/licenses.json | python -m json.tool | grep -A 15 "IW-728887"
```

### Command Line - View purchases
```bash
# View all purchases
cat server/data/purchases.jsonl | while read line; do echo $line | python -m json.tool; echo "---"; done

# Count purchases
wc -l server/data/purchases.jsonl

# Find Gumroad purchases over $100
cat server/data/purchases.jsonl | python -c "import sys, json; [print(json.loads(line)['license_key']) for line in sys.stdin if json.loads(line).get('source')=='gumroad' and float(json.loads(line).get('price', 0)) > 100]"
```

---

## Tier to Duration Mapping

Used by webhooks.py when creating licenses:

| Tier | Duration (days) | Expiry |
|------|-----------------|--------|
| Lifetime | 36500 | ~100 years from now |
| Yearly | 365 | 1 year from now |
| 6-Month | 180 | 6 months from now |
| 3-Month | 90 | 3 months from now |
| Monthly | 30 | 1 month from now |
| (Default) | 365 | 1 year from now |

---

## Validation Rules

### licenses.json Rules
- ✅ Must have valid email address
- ✅ expiry_date must be >= created_date
- ✅ is_active must be boolean
- ✅ hardware_id must be null until first validation
- ✅ purchase_source should match known platforms

### purchases.jsonl Rules
- ✅ Must have license_key (links to licenses.json)
- ✅ source must be one of: gumroad, stripe, direct, paypal
- ✅ price must be numeric (stored as string for precision)
- ✅ currency must be 3-letter ISO code (lowercase)
- ✅ timestamps must be ISO 8601 format
- ✅ boolean fields must be true/false

---

## Migration Path (If Upgrading Existing System)

If you have old licenses.json with bloated structure:

```python
import json
from datetime import datetime

# Load old licenses
with open('server/data/licenses_backup.json', 'r') as f:
    old_licenses = json.load(f)

# Convert to new format
new_licenses = {}
purchases = []

for key, old_data in old_licenses.items():
    # Create lean license
    new_licenses[key] = {
        'email': old_data['email'],
        'customer_name': old_data.get('customer_name', ''),
        'created_date': old_data['created_date'],
        'expiry_date': old_data['expiry_date'],
        'is_active': old_data.get('is_active', True),
        'hardware_id': old_data.get('hardware_id'),
        'device_name': old_data.get('device_name'),
        'last_validation': old_data.get('last_validation'),
        'validation_count': old_data.get('validation_count', 0),
        'purchase_source': old_data.get('purchase_source', 'unknown'),
        'purchase_id': old_data.get('purchase_id')
    }
    
    # Extract purchase info
    if 'source' in old_data:
        purchase = {
            'timestamp': datetime.now().isoformat(),
            'license_key': key,
            **{k: v for k, v in old_data.items() if k not in 
               ['email', 'customer_name', 'created_date', 'expiry_date', 
                'is_active', 'hardware_id', 'device_name', 'last_validation', 
                'validation_count', 'purchase_source', 'purchase_id']}
        }
        purchases.append(purchase)

# Save new format
with open('server/data/licenses.json', 'w') as f:
    json.dump(new_licenses, f, indent=2)

with open('server/data/purchases.jsonl', 'w') as f:
    for p in purchases:
        f.write(json.dumps(p) + '\n')

print(f"Migrated {len(new_licenses)} licenses")
print(f"Logged {len(purchases)} purchase records")
```

---

**All formats documented and ready for use!**
