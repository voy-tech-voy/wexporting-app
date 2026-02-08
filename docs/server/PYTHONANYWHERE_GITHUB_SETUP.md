# PythonAnywhere GitHub Integration Setup Guide

**Purpose:** Enable your PythonAnywhere server to pull code directly from GitHub and keep it in sync

---

## Step 1: Generate SSH Key on PythonAnywhere

### 1.1 Open PythonAnywhere Bash Console

1. Log in to https://www.pythonanywhere.com
2. Go to **Consoles** tab
3. Click **Bash** to open a terminal

### 1.2 Generate SSH Key

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
```

This creates:
- `~/.ssh/id_rsa` (private key - keep secret)
- `~/.ssh/id_rsa.pub` (public key - add to GitHub)

### 1.3 Display Public Key

```bash
cat ~/.ssh/id_rsa.pub
```

Copy the entire output.

---

## Step 2: Add SSH Key to GitHub

### 2.1 Go to GitHub Settings

1. Log in to https://github.com
2. Click your **profile icon** (top right)
3. Go to **Settings**
4. Click **SSH and GPG keys** (left sidebar)
5. Click **New SSH key**

### 2.2 Add the Key

- **Title:** PythonAnywhere Server
- **Key type:** Authentication Key
- **Key:** Paste the content from `~/.ssh/id_rsa.pub`
- Click **Add SSH key**

### 2.3 Test SSH Connection

Back in PythonAnywhere Bash:

```bash
ssh -T git@github.com
```

You should see:
```
Hi voy-tech-voy! You've successfully authenticated, but GitHub does not provide shell access.
```

---

## Step 3: Clone Repository on PythonAnywhere

### 3.1 Choose a Directory

SSH into PythonAnywhere:

```bash
# Go to home directory
cd ~

# Create apps directory if needed
mkdir -p apps
cd apps
```

### 3.2 Clone Your Repository

```bash
git clone git@github.com:voy-tech-voy/wbf.git
cd wbf
```

**Verify clone succeeded:**
```bash
ls -la
# You should see: client/ server/ README.md etc.
```

---

## Step 4: Set Up Virtual Environment on PythonAnywhere

### 4.1 Create Virtual Environment

```bash
cd ~/apps/wbf

# Create venv
python3.10 -m venv venv

# Activate venv
source venv/bin/activate

# Install requirements
pip install -r server/requirements.txt
```

### 4.2 Verify Installation

```bash
pip list | grep Flask
# Should see Flask installed
```

---

## Step 5: Update PythonAnywhere Web App Configuration

### 5.1 Go to Web Apps

1. In PythonAnywhere dashboard
2. Go to **Web** tab
3. Click on your web app

### 5.2 Update WSGI Configuration

Click on the **WSGI configuration file** link. Update it:

```python
import sys
import os

# Add the project directory to sys.path
project_dir = '/home/wavyvoy/apps/wbf'
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Set up virtual environment
activate_this = '/home/wavyvoy/apps/wbf/venv/bin/activate_this.py'
with open(activate_this) as f:
    exec(f.read(), {'__file__': activate_this})

# Set Flask env
os.environ['FLASK_ENV'] = 'production'
os.environ['SECRET_KEY'] = 'your-secret-key-here'

# Import and run the app
from server.app import app as application
```

**Replace:**
- `/home/wavyvoy/` with your PythonAnywhere username path

### 5.3 Reload Web App

Click the **Reload** button on the Web tab.

---

## Step 6: Create Deployment Script (Optional)

### 6.1 Create Update Script

SSH to PythonAnywhere and create `~/apps/update_from_github.sh`:

```bash
#!/bin/bash

cd ~/apps/wbf

# Activate virtual environment
source venv/bin/activate

# Pull latest code
git pull origin master

# Install any new dependencies
pip install -r server/requirements.txt

# Reload web app (if needed)
# This requires manual reload or API call

echo "✅ Updated from GitHub successfully"
echo "⚠️  Remember to reload the web app in PythonAnywhere dashboard"
```

### 6.2 Make Script Executable

```bash
chmod +x ~/apps/update_from_github.sh
```

### 6.3 Run Script to Update

```bash
~/apps/update_from_github.sh
```

---

## Step 7: Create Automated Deployment (Using Tasks)

### 7.1 Set Up Scheduled Task

1. Go to **Tasks** tab in PythonAnywhere
2. Click **Create new scheduled task**
3. Set to run **daily** (or your preferred frequency)
4. Command:
   ```bash
   /home/wavyvoy/apps/update_from_github.sh
   ```

### 7.2 Alternative: Manual Pull Command

Whenever you want to update, SSH and run:

```bash
cd ~/apps/wbf && git pull origin master && source venv/bin/activate && pip install -r server/requirements.txt
```

---

## Step 8: Handle Sensitive Files on PythonAnywhere

### 8.1 Create Data Directory (NOT in git)

```bash
mkdir -p ~/apps/wbf/server/data
```

### 8.2 Create licenses.json

```bash
cat > ~/apps/wbf/server/data/licenses.json << 'EOF'
{}
EOF
```

### 8.3 Create trials.json

```bash
cat > ~/apps/wbf/server/data/trials.json << 'EOF'
{}
EOF
```

### 8.4 Set .env Variables

Go to **Web** tab → **WSGI configuration file** and set environment variables at the top:

```python
import os

# Set environment variables (secrets)
os.environ['SECRET_KEY'] = 'your-production-secret-key-here'
os.environ['ADMIN_PASSWORD'] = 'your-admin-password-here'
os.environ['SMTP_SERVER'] = 'smtp.gmail.com'
os.environ['SMTP_PORT'] = '587'
os.environ['SMTP_USERNAME'] = 'your-email@gmail.com'
os.environ['SMTP_PASSWORD'] = 'your-app-password-here'
os.environ['FROM_EMAIL'] = 'noreply@yourapp.com'
os.environ['FLASK_ENV'] = 'production'

# ... rest of WSGI config
```

Or use **Web** tab → **Environment variables** section if available.

---

## Step 9: Verify Everything Works

### 9.1 Test Server Status Endpoint

```bash
curl https://wavyvoy.pythonanywhere.com/api/v1/status
```

Should return:
```json
{"status": "online", "version": "1.0.0"}
```

### 9.2 Test License Validation

```bash
curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/license/validate \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","license_key":"IW-123456-ABCDEF12","hardware_id":"abc123","device_name":"Test"}'
```

### 9.3 Monitor Error Logs

In PythonAnywhere **Web** tab, check:
- **Error log** for Python errors
- **Server log** for request logs

---

## Step 10: Update Workflow

### After Each GitHub Push:

**Option A: Manual Update**
```bash
# SSH to PythonAnywhere and run:
cd ~/apps/wbf && git pull origin master
```

**Option B: Automatic via Scheduled Task**
- Task runs daily and pulls automatically
- Check logs to verify success

**Option C: Webhook (Advanced)**
- Set up GitHub webhook to trigger server update
- Requires additional setup beyond this guide

---

## Troubleshooting

### Issue: "Permission denied (publickey)"

**Solution:**
1. Verify SSH key is added to GitHub
2. Test: `ssh -T git@github.com`
3. Regenerate key if needed

### Issue: "fatal: Could not read from remote repository"

**Solution:**
1. Verify repo URL: `git remote -v`
2. Should show: `git@github.com:voy-tech-voy/wbf.git`
3. Update if needed: `git remote set-url origin git@github.com:voy-tech-voy/wbf.git`

### Issue: "ModuleNotFoundError" after git pull

**Solution:**
```bash
source ~/apps/wbf/venv/bin/activate
pip install -r ~/apps/wbf/server/requirements.txt
```

### Issue: Web app still showing old code

**Solution:**
1. Go to **Web** tab
2. Click **Reload** button
3. Wait 10 seconds for reload to complete
4. Test endpoint again

### Issue: Can't find licenses.json

**Solution:**
```bash
# Verify file exists
ls -la ~/apps/wbf/server/data/

# Create if missing
mkdir -p ~/apps/wbf/server/data
echo '{}' > ~/apps/wbf/server/data/licenses.json
```

---

## Summary of Deployment Steps

| Step | Action | Status |
|------|--------|--------|
| 1 | Generate SSH key on PythonAnywhere | ☐ |
| 2 | Add SSH key to GitHub | ☐ |
| 3 | Clone repo to `~/apps/wbf/` | ☐ |
| 4 | Create virtual environment | ☐ |
| 5 | Update WSGI configuration | ☐ |
| 6 | Create sensitive data files | ☐ |
| 7 | Set environment variables | ☐ |
| 8 | Reload web app | ☐ |
| 9 | Test API endpoints | ☐ |
| 10 | Set up auto-update script (optional) | ☐ |

---

## Quick Reference Commands

### Pull Latest Code
```bash
cd ~/apps/wbf && git pull origin master
```

### Activate Venv
```bash
source ~/apps/wbf/venv/bin/activate
```

### Check Logs
```bash
tail -f ~/apps/wbf/server.log
```

### Restart App
```bash
touch /var/www/wavyvoy_pythonanywhere_com_wsgi.py
```

### View Git Status
```bash
cd ~/apps/wbf && git status
```

---

## Next Steps

1. ✅ Complete all 10 steps above
2. ✅ Test all API endpoints from your client
3. ✅ Monitor logs for errors
4. ✅ Set up automated updates if desired
5. ✅ Document any custom configurations

---

**Document Version:** 1.0  
**Last Updated:** December 17, 2025  
**Ready for:** Production Deployment
