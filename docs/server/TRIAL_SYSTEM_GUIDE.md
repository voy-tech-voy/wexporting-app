# Trial System Implementation Guide

## Overview

Complete trial system implementation with abuse prevention, offline restrictions, and grace periods for paid licenses.

## Features Implemented

### ✅ Trial License Management
- **1-day trial duration**
- **Immediate device binding** (no device transfers for trials)
- **Online-only validation** (trials require internet connection)
- **Dual abuse prevention** (one trial per email AND one trial per hardware_id)

### ✅ Paid License Offline Support
- **3-day offline grace period** after last online validation
- **First activation requires online** connection
- **Automatic grace period enforcement**

### ✅ API Endpoints

#### Trial Endpoints

**1. Check Trial Eligibility**
```
POST /api/v1/webhooks/trial/check-eligibility
```
Request:
```json
{
  "email": "user@example.com",
  "hardware_id": "ABC123XYZ"
}
```
Response:
```json
{
  "eligible": true,
  "message": "User is eligible for a trial"
}
```

**2. Create Trial License**
```
POST /api/v1/webhooks/trial/create
```
Request:
```json
{
  "email": "user@example.com",
  "hardware_id": "ABC123XYZ",
  "device_name": "MacBook Pro"
}
```
Response:
```json
{
  "success": true,
  "license_key": "IW-741696-ACB1830F",
  "expires": "2025-12-15T20:48:16.365558",
  "message": "Trial license created successfully"
}
```

**3. Get Trial Status**
```
GET /api/v1/webhooks/trial/status/<license_key>
```
Response:
```json
{
  "success": true,
  "is_trial": true,
  "is_active": true,
  "expires": "2025-12-15T...",
  "email": "user@example.com",
  "device_name": "MacBook Pro",
  "hardware_id": "ABC123XYZ"
}
```

**4. Check Offline Availability**
```
POST /api/v1/webhooks/license/offline-check/<license_key>
```
Request:
```json
{
  "email": "user@example.com",
  "hardware_id": "ABC123XYZ"
}
```
Response (for paid licenses):
```json
{
  "can_use_offline": true,
  "is_trial": false,
  "days_since_last_validation": 2,
  "grace_period_remaining": 1,
  "message": "Offline use available"
}
```

Response (for trials):
```json
{
  "can_use_offline": false,
  "is_trial": true,
  "message": "Trial licenses require internet connection"
}
```

## Validation Flow

### Trial License Validation

```python
# Client calls validation endpoint
POST /api/v1/licenses/validate
{
  "email": "user@example.com",
  "license_key": "IW-...",
  "hardware_id": "ABC123",
  "device_name": "MacBook Pro",
  "is_offline": false  # Must be false for trials
}

# Server response
{
  "success": true,
  "message": "License validated successfully",
  "expires": "2025-12-15T...",
  "is_trial": true
}
```

**If client tries offline validation for trial:**
```json
{
  "success": false,
  "error": "trial_requires_online",
  "message": "Trial licenses require internet connection for validation"
}
```

### Paid License Validation (Offline)

```python
# Client calls validation endpoint
POST /api/v1/licenses/validate
{
  "email": "user@example.com",
  "license_key": "IW-...",
  "hardware_id": "ABC123",
  "device_name": "MacBook Pro",
  "is_offline": true
}

# If within 3-day grace period:
{
  "success": true,
  "message": "License validated successfully",
  "expires": "2026-01-13T...",
  "is_trial": false
}

# If beyond 3-day grace period:
{
  "success": false,
  "error": "offline_grace_expired",
  "message": "Please connect to the internet to validate your license"
}
```

## Abuse Prevention

### Email-Based Prevention
- System checks if any license exists with same email
- If found and duration ≤ 1 day, blocks trial creation
- Error: `trial_already_used_email`

### Device-Based Prevention
- System checks if any license exists with same hardware_id
- If found and duration ≤ 1 day, blocks trial creation
- Error: `trial_already_used_device`

### Implementation in license_manager.py

```python
def check_trial_eligibility(self, email, hardware_id):
    """Check if user is eligible for a trial"""
    licenses = self.load_licenses()
    
    # Check email
    for license_key, license_data in licenses.items():
        if license_data.get('email') == email:
            created = datetime.fromisoformat(license_data['created_date'])
            expiry = datetime.fromisoformat(license_data['expiry_date'])
            days_diff = (expiry - created).days
            
            if days_diff <= 1:  # It's a trial
                return {
                    'eligible': False,
                    'reason': 'trial_already_used_email'
                }
    
    # Check hardware_id
    for license_key, license_data in licenses.items():
        if license_data.get('hardware_id') == hardware_id:
            # Similar check...
            
    return {'eligible': True}
```

## Client Integration

### Desktop App Flow

1. **User clicks "Try Free" button**
2. **App collects:**
   - Email address
   - Hardware ID (from system)
   - Device name (optional)

3. **App calls eligibility check:**
```python
response = requests.post(
    'https://your-server.com/api/v1/webhooks/trial/check-eligibility',
    json={
        'email': email,
        'hardware_id': hardware_id
    }
)
```

4. **If eligible, create trial:**
```python
response = requests.post(
    'https://your-server.com/api/v1/webhooks/trial/create',
    json={
        'email': email,
        'hardware_id': hardware_id,
        'device_name': device_name
    }
)

license_key = response.json()['license_key']
# Save license_key to app config
```

5. **On app startup, validate license:**
```python
# Check if online
is_offline = not check_internet_connection()

response = requests.post(
    'https://your-server.com/api/v1/licenses/validate',
    json={
        'email': email,
        'license_key': license_key,
        'hardware_id': hardware_id,
        'device_name': device_name,
        'is_offline': is_offline
    }
)

if response.json()['success']:
    # Allow app to run
    if response.json()['is_trial']:
        # Show "Trial - X days remaining"
else:
    # Handle error
    error = response.json()['error']
    if error == 'trial_requires_online':
        # Show "Trial requires internet connection"
    elif error == 'offline_grace_expired':
        # Show "Please connect to validate license"
```

## Testing

### Run Test Suite
```bash
python test_trial_system.py
```

### Test Coverage
✅ Trial eligibility checking  
✅ Trial creation  
✅ Trial identification (is_trial_license)  
✅ Immediate device binding  
✅ Online validation for trials  
✅ Offline validation blocking for trials  
✅ Paid license offline grace period (3 days)  
✅ Email-based abuse prevention  
✅ Device-based abuse prevention  

## Data Structure

### Trial License in licenses.json
```json
{
  "IW-741696-ACB1830F": {
    "email": "user@example.com",
    "created_date": "2025-12-14T20:48:16.365558",
    "expiry_date": "2025-12-15T20:48:16.365558",
    "is_active": true,
    "hardware_id": "ABC123XYZ",
    "device_name": "MacBook Pro",
    "last_validation": "2025-12-14T20:48:16.365558",
    "validation_count": 0,
    "source_license_key": null
  }
}
```

### Trial Purchase Record in purchases.jsonl
```json
{
  "timestamp": "2025-12-14T20:48:16.365558",
  "license_key": "IW-741696-ACB1830F",
  "source": "trial",
  "is_trial": true,
  "product_name": "ImgApp Trial",
  "tier": "trial",
  "price": 0,
  "currency": "USD",
  "purchase_date": "2025-12-14T20:48:16.365558",
  "is_recurring": false
}
```

## Key Methods

### license_manager.py

| Method | Purpose |
|--------|---------|
| `check_trial_eligibility(email, hardware_id)` | Check if user can create trial |
| `create_trial_license(email, hardware_id, device_name)` | Create 1-day trial |
| `is_trial_license(license_key)` | Check if license is trial |
| `validate_license(..., is_offline=False)` | Validate with offline support |

## Security Considerations

1. **Rate Limiting**: Add rate limiting to trial creation endpoint
2. **Email Verification**: Consider email verification before trial
3. **Hardware ID Spoofing**: Use secure hardware ID generation
4. **IP Tracking**: Log IP addresses for additional abuse prevention

## Next Steps

1. ✅ Trial system implemented
2. ⏳ Create landing page for trial distribution
3. ⏳ Integrate trial endpoints with client app
4. ⏳ Deploy to PythonAnywhere
5. ⏳ Configure Gumroad for paid purchases
6. ⏳ Monitor trial abuse patterns

## Support

For questions or issues:
- Check test_trial_system.py for examples
- Review API responses for error messages
- Check server/data/purchases.jsonl for audit trail
