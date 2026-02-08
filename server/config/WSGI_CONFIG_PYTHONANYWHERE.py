# ============================================================================
# PythonAnywhere WSGI Configuration for ImgApp Server
# This file is used by PythonAnywhere to run your Flask application
# ============================================================================

import sys
import os

# ============================================================================
# 1. ADD SERVER DIRECTORY TO PYTHON PATH
# ============================================================================
# Add BOTH the project root and the server directory to ensure all imports work
project_dir = '/home/wavyvoy/apps/wbf'
server_dir = '/home/wavyvoy/apps/wbf/server'

if project_dir not in sys.path:
    sys.path.insert(0, project_dir)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

print(f"✅ Added project directory to path: {project_dir}")
print(f"✅ Added server directory to path: {server_dir}")

# ============================================================================
# 2. ACTIVATE VIRTUAL ENVIRONMENT
# ============================================================================
# This ensures all imports use the venv's installed packages
venv_dir = '/home/wavyvoy/apps/wbf/venv'
activate_this = os.path.join(venv_dir, 'bin', 'activate_this.py')
try:
    with open(activate_this) as f:
        exec(f.read(), {'__file__': activate_this})
    print(f"✅ Virtual environment activated: {venv_dir}")
except FileNotFoundError:
    print(f"⚠️  Virtual environment not found at: {venv_dir}")

# ============================================================================
# 3. SET FLASK ENVIRONMENT
# ============================================================================
os.environ['FLASK_ENV'] = 'production'
print(f"✅ Set FLASK_ENV to production")

# ============================================================================
# 4. SET SECURITY CONFIGURATION
# ============================================================================
# Generate a strong random SECRET_KEY on production - DO NOT hardcode
os.environ['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY',
    'prod-secret-key-change-me-in-pythonanywhere'
)
print(f"✅ SECRET_KEY configured")

# ============================================================================
# 5. SET SMTP CONFIGURATION FOR EMAIL NOTIFICATIONS
# ============================================================================
# These values can also be set in PythonAnywhere Web tab -> Environment variables
os.environ['SMTP_SERVER'] = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
os.environ['SMTP_PORT'] = os.environ.get('SMTP_PORT', '587')
os.environ['SMTP_USERNAME'] = os.environ.get(
    'SMTP_USERNAME',
    'voytechapps@gmail.com'  # CHANGE THIS if different
)
os.environ['SMTP_PASSWORD'] = os.environ.get(
    'SMTP_PASSWORD',
    'smpt pass word text'  # CHANGE THIS to your actual password
)
os.environ['FROM_EMAIL'] = os.environ.get(
    'FROM_EMAIL',
    'voytechapps@gmail.com'  # Email address to send notifications from
)
print(f"✅ SMTP configured: {os.environ.get('SMTP_USERNAME')}")

# ============================================================================
# 6. SET SECURITY CONFIGURATION (ADMIN API)
# ============================================================================
# !!! IMPORTANT: Set these values below after deployment !!!

# Admin API key for protected endpoints like /license/create
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
# Generated key: 9u3jbn1X9npKbltLQ7WCGr_Fgl8Luok9r_adGbnGoKk
os.environ['ADMIN_API_KEY'] = os.environ.get(
    'ADMIN_API_KEY',
    ''  # SET THIS to your admin API key
)

if os.environ.get('ADMIN_API_KEY'):
    print(f"✅ Admin API key configured")
else:
    print(f"⚠️  WARNING: ADMIN_API_KEY not set - admin endpoints disabled!")


# ============================================================================
# 7. CREATE THE FLASK APPLICATION INSTANCE
# ============================================================================
# Import the factory function and create the app with current configuration
# Note: We import from 'app' directly because server_dir is in sys.path
try:
    from app import create_app
    application = create_app()
    print(f"✅ Flask application created successfully")
except ImportError as e:
    print(f"❌ ERROR: Could not import create_app: {e}")
    raise
except Exception as e:
    print(f"❌ ERROR: Could not create application: {e}")
    raise

# ============================================================================
# 8. LOGGING FOR DEBUGGING
# ============================================================================
# Log all environment-related info for troubleshooting
print("=" * 70)
print("PYTHONANYWHERE WSGI CONFIGURATION COMPLETE")
print("=" * 70)
print(f"Project Directory: {project_dir}")
print(f"Virtual Environment: {venv_dir}")
print(f"Flask Environment: {os.environ.get('FLASK_ENV')}")
print(f"SMTP Server: {os.environ.get('SMTP_SERVER')}:{os.environ.get('SMTP_PORT')}")
print(f"Data Folder: {os.path.join(project_dir, 'server/data')}")
print("=" * 70)
