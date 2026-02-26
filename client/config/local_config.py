"""
Development mode bypass for ImgApp
This creates a simple bypass file for development testing
"""

# This tells the config that we're in development mode
DEVELOPMENT_MODE = True

# Optional: Use local license validation only
USE_LOCAL_VALIDATION_ONLY = True

# API override for local testing
API_BASE_URL = "http://localhost:5001"

# Force Premium Status (None = use real consistent state, True/False = force override)
PREMIUM_OVERRIDE = False
