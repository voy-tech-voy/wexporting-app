# Pre-Build Checklist for MS Store Submission

## Overview

Your build system is **functional** but needs updates to support the new store-native authentication and energy system. This checklist ensures a successful build before MS Store submission.

---

## ✅ Critical Updates Required

### 1. **Update PyInstaller Spec File**

**File**: [`build/specs/production.spec`](file:///v:/_MY_APPS/ImgApp_1/build/specs/production.spec)

**Issues**:
- ❌ Uses PyQt5 (app refactored to PyQt6)
- ❌ Missing `winrt` hidden imports for MS Store APIs
- ❌ Missing new `auth` module imports

**Required Changes**:

```diff
# Line 9: Update hidden imports
hiddenimports=[
    'client.utils.crash_reporter',
    'client.utils.error_reporter', 
    'client.utils.hardware_id',
    'requests',
-   'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui'
+   'PyQt6.QtCore', 'PyQt6.QtWidgets', 'PyQt6.QtGui',
+   'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'PyQt6.sip',
+   # WinRT for MS Store APIs
+   'winrt', 'winrt.windows.services.store',
+   # New auth modules
+   'client.core.auth.ms_store_provider',
+   'client.core.auth.apple_store_provider',
+   'client.core.auth.store_auth_provider',
],
```

**Action**: Update `production.spec` or let `build_production.py` generate it dynamically.

---

### 2. **Update Build Script Dependencies**

**File**: [`build/scripts/build_production.py`](file:///v:/_MY_APPS/ImgApp_1/build/scripts/build_production.py)

**Current Hidden Imports** (Lines 138-147):
```python
"--hidden-import=PyQt6.QtCore",
"--hidden-import=PyQt6.QtWidgets",
"--hidden-import=PyQt6.QtGui",
"--hidden-import=PyQt6.QtSvg",
"--hidden-import=PyQt6.QtSvgWidgets",
"--hidden-import=PyQt6.sip",
```

**Add These**:
```python
# WinRT for MS Store
"--hidden-import=winrt",
"--hidden-import=winrt.windows.services.store",
# Auth modules
"--hidden-import=client.core.auth",
"--hidden-import=client.core.auth.ms_store_provider",
"--hidden-import=client.core.auth.apple_store_provider",
"--hidden-import=client.core.auth.store_auth_provider",
# Energy API client
"--hidden-import=client.core.energy_api_client",
```

**Location**: Insert after line 147 in `build_production.py`

---

### 3. **Install WinRT Package**

**Required for MS Store APIs**:

```bash
# In your virtual environment
cd v:\_MY_APPS\ImgApp_1
.\imgapp_venv\Scripts\activate
pip install winrt
```

**Verify**:
```python
python -c "from winrt.windows.services.store import StoreContext; print('WinRT OK')"
```

---

### 4. **Update Requirements.txt**

Add to `requirements.txt`:
```txt
winrt>=1.0.0
PyJWT>=2.8.0
```

---

## 🔧 Azure AD Configuration (Server-Side)

Before building, ensure your **server** has Azure AD credentials configured:

### Step 1: Create Azure AD App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
   - Name: "ImgApp Store Validation"
   - Account types: "Single tenant"
4. Note:
   - **Application (client) ID**
   - **Directory (tenant) ID**

### Step 2: Add API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **APIs my organization uses**
4. Search for "Windows Store" or "Microsoft Store"
5. Add: `https://onestore.microsoft.com/.default`
6. Click **Grant admin consent**

### Step 3: Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Description: "Store Validation Secret"
4. Expiry: 24 months
5. **Copy the secret value** (only shown once!)

### Step 4: Update Server Environment

On your server (PythonAnywhere or local):

```bash
# Add to .env or environment variables
export MSSTORE_TENANT_ID="<your_tenant_id>"
export MSSTORE_CLIENT_ID="<your_client_id>"
export MSSTORE_CLIENT_SECRET="<your_client_secret>"
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
```

**Test Server**:
```bash
cd v:\_MY_APPS\ImgApp_1\server
python -c "from config.settings import Config; print(f'Tenant: {Config.MSSTORE_TENANT_ID[:8]}...')"
```

---

## 📦 MSIX Packaging Requirements

### 1. **Install WiX Toolset**

**Current Status**: `build_msix.py` expects WiX at:
- `C:/Program Files (x86)/WiX Toolset v3.11/bin`
- `C:/Program Files/WiX Toolset v3.11/bin`

**Install**:
1. Download from [WiX Toolset](https://wixtoolset.org/)
2. Install to default location
3. Verify: `"C:\Program Files (x86)\WiX Toolset v3.11\bin\candle.exe"`

### 2. **Create App Manifest**

**Required for MSIX**: `Package.appxmanifest`

Create at `v:\_MY_APPS\ImgApp_1\Package.appxmanifest`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">
  
  <Identity Name="YourPublisher.ImgApp"
            Publisher="CN=YourPublisher"
            Version="1.0.0.0" />
  
  <Properties>
    <DisplayName>ImgApp</DisplayName>
    <PublisherDisplayName>Your Company</PublisherDisplayName>
    <Logo>client\assets\icons\app_icon.png</Logo>
  </Properties>
  
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.22000.0" />
  </Dependencies>
  
  <Resources>
    <Resource Language="en-us" />
  </Resources>
  
  <Applications>
    <Application Id="ImgApp" Executable="ImgApp.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="ImgApp"
                          Description="Professional image and video conversion tool"
                          BackgroundColor="transparent"
                          Square150x150Logo="client\assets\icons\app_icon.png"
                          Square44x44Logo="client\assets\icons\app_icon.png">
      </uap:VisualElements>
    </Application>
  </Applications>
  
  <Capabilities>
    <Capability Name="internetClient" />
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
```

### 3. **Prepare App Icons**

**Required Sizes** for MS Store:
- 44x44 (Small tile)
- 150x150 (Medium tile)
- 300x300 (Store logo)
- 1920x1080 (Screenshots, 3-5 images)

**Current Location**: `client/assets/icons/app_icon.ico`, `app_icon.png`

**Action**: Ensure PNG versions exist at all required sizes.

---

## 🧪 Pre-Build Testing

### 1. **Test Server Endpoints**

```bash
# Start server
cd v:\_MY_APPS\ImgApp_1\server
python app.py

# Test JWT creation (in another terminal)
curl -X POST http://localhost:5000/api/v1/store/validate-receipt \
  -H "Content-Type: application/json" \
  -d '{"receipt_data":"test","platform":"msstore","product_id":"imgapp_lifetime"}'
```

**Expected**: Error about invalid receipt (but endpoint works)

### 2. **Test Client Imports**

```bash
cd v:\_MY_APPS\ImgApp_1
.\imgapp_venv\Scripts\python.exe -c "
from client.core.auth import get_store_provider
from client.core.energy_manager import EnergyManager
print('Imports OK')
"
```

### 3. **Test WinRT (Windows Only)**

```bash
.\imgapp_venv\Scripts\python.exe -c "
try:
    from winrt.windows.services.store import StoreContext
    print('WinRT available')
except ImportError:
    print('WinRT not installed - install with: pip install winrt')
"
```

---

## 🏗️ Build Process

Once all checks pass, run the build:

### Step 1: Build Executable

```bash
cd v:\_MY_APPS\ImgApp_1\build\bat
.\build_production.bat 1.0
```

**Output**: `ImgApp_Releases/v1.0/ImgApp-v1.0/ImgApp-v1.0.exe`

### Step 2: Build MSI (Optional)

```bash
cd v:\_MY_APPS\ImgApp_1\build\scripts
python build_msix.py
```

**Output**: `ImgApp_Releases/v1.0/imgapp-v1.0-installer.msi`

### Step 3: Convert to MSIX

Use **MSIX Packaging Tool** (from Microsoft Store):
1. Open MSIX Packaging Tool
2. Select "Application package" → "Create package"
3. Choose the MSI file
4. Follow wizard to create MSIX

**Output**: `ImgApp_Releases/v1.0/imgapp-v1.0.msix`

---

## ✅ Final Checklist

Before submitting to MS Store:

- [ ] **Dependencies**
  - [ ] `winrt` installed in venv
  - [ ] `PyJWT` installed
  - [ ] PyInstaller spec updated with new imports
  
- [ ] **Server Configuration**
  - [ ] Azure AD app created
  - [ ] API permissions granted
  - [ ] Environment variables set
  - [ ] Server endpoints tested
  
- [ ] **Build System**
  - [ ] WiX Toolset installed
  - [ ] `build_production.py` updated with new hidden imports
  - [ ] App icons prepared (all sizes)
  - [ ] `Package.appxmanifest` created
  
- [ ] **Testing**
  - [ ] Server endpoints respond correctly
  - [ ] Client imports work
  - [ ] WinRT available (if on Windows)
  - [ ] Executable builds successfully
  
- [ ] **MSIX Package**
  - [ ] MSI created
  - [ ] MSIX converted
  - [ ] MSIX installs locally
  - [ ] App launches from Start menu

---

## 🚨 Known Issues & Solutions

### Issue: "Module 'winrt' not found"

**Solution**:
```bash
pip install winrt
```

### Issue: "PyQt5 module not found"

**Solution**: Update `production.spec` to use PyQt6 (see section 1)

### Issue: "Azure AD credentials not configured"

**Solution**: Complete Azure AD setup (see section 4)

### Issue: "WiX Toolset not found"

**Solution**: Install WiX Toolset v3.11 from https://wixtoolset.org/

---

## 📝 Summary

**Immediate Actions**:
1. ✅ Update `build_production.py` with new hidden imports (winrt, auth modules)
2. ✅ Install `winrt` package: `pip install winrt`
3. ✅ Set up Azure AD app registration
4. ✅ Add environment variables to server
5. ✅ Test build process

**Estimated Time**: 2-3 hours

**After Build**:
- Test MSIX installation locally
- Prepare Partner Center account
- Submit to MS Store

Your build system is **90% ready** - just needs dependency updates and Azure AD configuration!
