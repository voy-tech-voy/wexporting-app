# Mac Development Guide: Implementing App Store Support

So you're on a Mac! This guide covers the steps to implement the pending Client-Side App Store support.

## 1. Environment Setup

### Install Dependencies
You'll need `pyobjc` to bridge Python with native macOS frameworks (StoreKit).

```bash
pip install pyobjc-framework-StoreKit
```

### Xcode Setup
- Install Xcode.
- Ensure your Apple ID is signed in.
- Create a test user in App Store Connect (Sandbox Tester).

## 2. Implement `AppleStoreProvider`

Edit `client/core/auth/apple_store_provider.py`. It is currently a stub.

### Key Implementation Steps using StoreKit 2
Wait for `pyobjc` support for StoreKit 2 (some features might need Swift bridge).

**Recommended Approach: Hybrid Swift/Python**
Since StoreKit 2 is Swift-only (async/await), using `pyobjc` might be tricky. The most robust way is to create a small Swift helper executable or dylib.

**Option A: Pure Python (via pyobjc)**
*Only possible if StoreKit 1 is sufficient or if pyobjc has updated wrapper.*

```python
import StoreKit
from Foundation import NSBundle

class AppleStoreProvider(IStoreAuthProvider):
    def request_purchase(self, product_id):
        # 1. Get Product
        request = SKProductsRequest.alloc().initWithProductIdentifiers_([product_id])
        request.setDelegate_(self)
        request.start()
        # ... logic to handle delegate callbacks ...
```

**Option B: Swift Helper (RECOMMENDED)**
Write a small CLI tool `store_helper` in Swift that:
1. Takes a product ID as argument.
2. Calls `Product.purchase()`.
3. Returns JSON with transaction info.

Then calls it from Python:
```python
import subprocess
import json

def request_purchase(self, product_id):
    result = subprocess.run(["./store_helper", "buy", product_id], capture_output=True)
    data = json.loads(result.stdout)
    return self.validate_receipt(data['originalTransactionId'])
```

## 3. Testing
1.  Run the app.
2.  Click "Buy Energy".
3.  The macOS "Sign in to App Store" dialog should appear (Sandbox).
4.  Enter Sandbox Tester credentials.
5.  Verify the app gets the `transactionId`.
6.  Verify the server validation succeeds (logs on server).

## 4. Server Validation
The server logic is already implemented in `server/services/store_validation.py`.
It expects `receipt_data` to be the `originalTransactionId`.

Ensure your `server/config/settings.py` has the Apple Keys set up.
