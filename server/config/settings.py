import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    DATA_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    LICENSES_FILE = os.path.join(DATA_FOLDER, 'licenses.json')
    TRIALS_FILE = os.path.join(DATA_FOLDER, 'trials.json')
    
    # Debug mode
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # Email Configuration
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    FROM_EMAIL = os.environ.get('FROM_EMAIL', 'noreply@imagewave.com')
    
    

    # ========================================================================
    # MICROSOFT STORE CONFIGURATION
    # ========================================================================
    # Azure AD app registration for MS Store API
    MSSTORE_TENANT_ID = os.environ.get('MSSTORE_TENANT_ID')  # Azure AD tenant ID
    MSSTORE_CLIENT_ID = os.environ.get('MSSTORE_CLIENT_ID')  # Azure AD app client ID
    MSSTORE_CLIENT_SECRET = os.environ.get('MSSTORE_CLIENT_SECRET')  # Azure AD app secret
    
    # Store-specific identifiers
    MSSTORE_STORE_ID = os.environ.get('MSSTORE_STORE_ID')  # Your MS Store seller ID
    MSSTORE_APP_ID = os.environ.get('MSSTORE_APP_ID')  # Your app's Store ID
    
    # Enable MS Store webhook verification
    VERIFY_MSSTORE_WEBHOOK = os.environ.get('VERIFY_MSSTORE_WEBHOOK', 'true').lower() == 'true'
    
    # ========================================================================
    # ADMIN & SECURITY
    # ========================================================================
    ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')  # Set in PythonAnywhere
