"""
Configuration settings for ImageWave Converter
"""

import os
import sys

class Config:
    """Base configuration"""
    
    # API Configuration
    API_BASE_URL = "https://wavyvoy.pythonanywhere.com"  # Your PythonAnywhere API
    API_TIMEOUT = 30
    
    # API Version Prefix
    API_PREFIX = "/api/v1"
    
    # License Configuration
    LICENSE_VALIDATION_ENDPOINT = f"{API_PREFIX}/license/validate"
    LICENSE_TRANSFER_ENDPOINT = f"{API_PREFIX}/license/transfer"
    LICENSE_FORGOT_ENDPOINT = f"{API_PREFIX}/license/forgot"
    
    # Trial Configuration
    TRIAL_CHECK_ELIGIBILITY_ENDPOINT = f"{API_PREFIX}/trial/check-eligibility"
    TRIAL_CREATE_ENDPOINT = f"{API_PREFIX}/trial/create"
    TRIAL_STATUS_ENDPOINT = f"{API_PREFIX}/trial/status"
    
    # Energy System Configuration (NEW)
    ENERGY_SYNC_ENDPOINT = f"{API_PREFIX}/energy/sync"
    ENERGY_RESERVE_ENDPOINT = f"{API_PREFIX}/energy/reserve"
    ENERGY_REPORT_ENDPOINT = f"{API_PREFIX}/energy/report"
    CONFIG_COSTS_ENDPOINT = f"{API_PREFIX}/config/costs"
    
    # Store Authentication Configuration (NEW)
    STORE_AUTH_LOGIN_ENDPOINT = f"{API_PREFIX}/auth/login"
    STORE_VALIDATE_RECEIPT_ENDPOINT = f"{API_PREFIX}/store/validate-receipt"
    
    # Application Configuration
    APP_NAME = "ImageWave Converter"
    APP_VERSION = "1.1.0"
    
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
    import local_config
    if hasattr(local_config, 'API_BASE_URL'):
        current_config.API_BASE_URL = local_config.API_BASE_URL
    if hasattr(local_config, 'DEVELOPMENT_MODE') and local_config.DEVELOPMENT_MODE:
        current_config.DEBUG = True
        print("Using local development server override")
except ImportError:
    pass  # No local config file

# Export commonly used values
API_BASE_URL = current_config.API_BASE_URL
VALIDATE_URL = f"{API_BASE_URL}{current_config.LICENSE_VALIDATION_ENDPOINT}"
TRANSFER_URL = f"{API_BASE_URL}{current_config.LICENSE_TRANSFER_ENDPOINT}"
FORGOT_LICENSE_URL = f"{API_BASE_URL}{current_config.LICENSE_FORGOT_ENDPOINT}"

# Trial System URLs
TRIAL_CHECK_ELIGIBILITY_URL = f"{API_BASE_URL}{current_config.TRIAL_CHECK_ELIGIBILITY_ENDPOINT}"
TRIAL_CREATE_URL = f"{API_BASE_URL}{current_config.TRIAL_CREATE_ENDPOINT}"
TRIAL_STATUS_URL = f"{API_BASE_URL}{current_config.TRIAL_STATUS_ENDPOINT}"

# Energy System URLs (NEW)
ENERGY_SYNC_URL = f"{API_BASE_URL}{current_config.ENERGY_SYNC_ENDPOINT}"
ENERGY_RESERVE_URL = f"{API_BASE_URL}{current_config.ENERGY_RESERVE_ENDPOINT}"
ENERGY_REPORT_URL = f"{API_BASE_URL}{current_config.ENERGY_REPORT_ENDPOINT}"
CONFIG_COSTS_URL = f"{API_BASE_URL}{current_config.CONFIG_COSTS_ENDPOINT}"

# Store Authentication URLs (NEW)
STORE_AUTH_LOGIN_URL = f"{API_BASE_URL}{current_config.STORE_AUTH_LOGIN_ENDPOINT}"
STORE_VALIDATE_RECEIPT_URL = f"{API_BASE_URL}{current_config.STORE_VALIDATE_RECEIPT_ENDPOINT}"
