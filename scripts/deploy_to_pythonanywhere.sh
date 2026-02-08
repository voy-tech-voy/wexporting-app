#!/bin/bash
# Deployment script for PythonAnywhere
# Run this script after SSHing into PythonAnywhere

set -e  # Exit on error

echo "=== Starting deployment ==="

# Navigate to project
echo "Navigating to project directory..."
cd ~/ImgApp_1

# Pull latest code
echo "Pulling latest code from GitHub..."
git pull origin master

# Create data directory
echo "Creating data directory..."
mkdir -p ~/ImgApp_1/server/data

# Initialize data files
echo "Initializing data files..."
echo '{}' > ~/ImgApp_1/server/data/licenses.json
touch ~/ImgApp_1/server/data/purchases.jsonl
echo '{}' > ~/ImgApp_1/server/data/trials.json

# Set permissions
echo "Setting file permissions..."
chmod 644 ~/ImgApp_1/server/data/*.json
chmod 644 ~/ImgApp_1/server/data/*.jsonl

echo "=== Deployment complete ==="
echo ""
echo "Next steps:"
echo "1. Go to https://www.pythonanywhere.com/user/wavyvoy/webapps/"
echo "2. Click the green 'Reload' button"
echo "3. Test the trial endpoints"
echo ""
echo "Or reload via command line with your API token:"
echo "curl -X POST https://www.pythonanywhere.com/api/v0/user/wavyvoy/webapps/wavyvoy.pythonanywhere.com/reload/ -H 'Authorization: Token YOUR_API_TOKEN'"
