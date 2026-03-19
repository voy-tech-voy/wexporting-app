"""
Configuration settings for webatchify
"""

import os
import sys
from client.version import APP_NAME, AUTHOR

class Config:
    """Base configuration"""
    
    # API Configuration
    API_BASE_URL = "https://wavyvoy.pythonanywhere.com"  # Your PythonAnywhere API
    API_TIMEOUT = 30
    
    # API Version Prefix
    API_PREFIX = "/api/v1"
    
    # Energy System Configuration
    ENERGY_SYNC_ENDPOINT = f"{API_PREFIX}/energy/sync"
    ENERGY_RESERVE_ENDPOINT = f"{API_PREFIX}/energy/reserve"
    ENERGY_REPORT_ENDPOINT = f"{API_PREFIX}/energy/report"
    CONFIG_COSTS_ENDPOINT = f"{API_PREFIX}/config/costs"
    
    # Store Authentication Configuration (NEW)
    STORE_AUTH_LOGIN_ENDPOINT = f"{API_PREFIX}/auth/login"
    STORE_VALIDATE_RECEIPT_ENDPOINT = f"{API_PREFIX}/store/validate-receipt"
    
    # Version Gateway Configuration (NEW)
    APP_CONFIG_ENDPOINT = f"{API_PREFIX}/app-config"
    MSSTORE_PRODUCT_ID = "9N6WKVSXSRCN"  # MS Store Product ID
    
    # Content Update Configuration (NEW)
    UPDATE_MANIFEST_ENDPOINT = f"{API_PREFIX}/updates/manifest"
    UPDATE_DOWNLOAD_PRESET_ENDPOINT = f"{API_PREFIX}/updates/download/preset"
    UPDATE_DOWNLOAD_ESTIMATOR_ENDPOINT = f"{API_PREFIX}/updates/download/estimator"
    
    # Application Configuration
    APP_VERSION = "1.0.0"
    APP_AUTHOR = AUTHOR
    
    # Development mode detection
    # Production mode when frozen (PyInstaller build)
    DEVELOPMENT_MODE = (
        not getattr(sys, 'frozen', False) and
        (getattr(sys, '_called_from_test', False) or __debug__)
    )

class DevelopmentConfig(Config):
    """Development configuration"""
    API_BASE_URL = "http://127.0.0.1:5005"
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    API_BASE_URL = "https://wavyvoy.pythonanywhere.com"  # Your PythonAnywhere API
    DEBUG = False

# Configuration selection
if Config.DEVELOPMENT_MODE:
    current_config = DevelopmentConfig()
else:
    current_config = ProductionConfig()

# Check for local override file
try:
    from . import local_config
    if hasattr(local_config, 'API_BASE_URL'):
        current_config.API_BASE_URL = local_config.API_BASE_URL
    if hasattr(local_config, 'DEVELOPMENT_MODE') and local_config.DEVELOPMENT_MODE:
        current_config.DEBUG = True
        print("Using local development server override")
    
    # Load Premium Override
    if hasattr(local_config, 'PREMIUM_OVERRIDE'):
        current_config.PREMIUM_OVERRIDE = local_config.PREMIUM_OVERRIDE
        print(f"Using local Premium Override: {current_config.PREMIUM_OVERRIDE}")
    else:
        current_config.PREMIUM_OVERRIDE = None
        
except ImportError:
    current_config.PREMIUM_OVERRIDE = None
    pass  # No local config file

# Export commonly used values
API_BASE_URL = current_config.API_BASE_URL
# Energy System URLs
ENERGY_SYNC_URL = f"{API_BASE_URL}{current_config.ENERGY_SYNC_ENDPOINT}"
ENERGY_RESERVE_URL = f"{API_BASE_URL}{current_config.ENERGY_RESERVE_ENDPOINT}"
ENERGY_REPORT_URL = f"{API_BASE_URL}{current_config.ENERGY_REPORT_ENDPOINT}"
CONFIG_COSTS_URL = f"{API_BASE_URL}{current_config.CONFIG_COSTS_ENDPOINT}"

# Store Authentication URLs (NEW)
STORE_AUTH_LOGIN_URL = f"{API_BASE_URL}{current_config.STORE_AUTH_LOGIN_ENDPOINT}"
STORE_VALIDATE_RECEIPT_URL = f"{API_BASE_URL}{current_config.STORE_VALIDATE_RECEIPT_ENDPOINT}"

# Version Gateway URLs (NEW)
APP_CONFIG_URL = f"{API_BASE_URL}{current_config.APP_CONFIG_ENDPOINT}"
MSSTORE_PRODUCT_ID = current_config.MSSTORE_PRODUCT_ID

# Development Overrides
PREMIUM_OVERRIDE = current_config.PREMIUM_OVERRIDE

# Energy endpoint HMAC secret — must match ENERGY_HMAC_KEY on the server.
# Set via ENERGY_HMAC_SECRET env var for installed builds.
# If absent, signature verification is skipped (backward-compatible).
ENERGY_HMAC_SECRET = os.environ.get('ENERGY_HMAC_SECRET')
