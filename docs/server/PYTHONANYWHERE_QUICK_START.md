# PythonAnywhere Deployment - Quick Start Guide

## Overview

You now have everything needed to deploy your ImgApp server to PythonAnywhere with automated GitHub synchronization.

---

## What's Been Set Up

### ✅ GitHub Repository
- Repository: https://github.com/voy-tech-voy/wbf
- All code committed and pushed
- No sensitive data in git (licenses, trials, .env protected by .gitignore)

### ✅ Server Code
- Production-ready Flask server with license validation
- New endpoints for login, trial, and forgot license
- Proper error handling and logging

### ✅ Client Code
- Login validates with server
- Trial activation communicates with server
- Forgot license retrieves key from server
- User-friendly error messages

### ✅ Documentation
- `PYTHONANYWHERE_GITHUB_SETUP.md` - Complete step-by-step guide
- `PYTHONANYWHERE_DEPLOYMENT_CHECKLIST.md` - Quick reference checklist
- All commands and configurations documented

---

## Deployment Steps (in order)

### Quick Start (10 Steps)

1. **Generate SSH Key** on PythonAnywhere
   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
   ```

2. **Add SSH Key to GitHub**
   - Copy: `cat ~/.ssh/id_rsa.pub`
   - Paste to: GitHub Settings → SSH and GPG keys → New SSH key

3. **Clone Repository**
   ```bash
   cd ~/apps && git clone git@github.com:voy-tech-voy/wbf.git
   ```

4. **Create Virtual Environment**
   ```bash
   cd ~/apps/wbf && python3.10 -m venv venv
   source venv/bin/activate
   pip install -r server/requirements.txt
   ```

5. **Update WSGI Configuration**
   - Go to PythonAnywhere **Web** tab
   - Edit WSGI configuration file
   - Update paths (see guide for template)
   - Click **Reload**

6. **Create Data Files**
   ```bash
   mkdir -p ~/apps/wbf/server/data
   echo '{}' > ~/apps/wbf/server/data/licenses.json
   echo '{}' > ~/apps/wbf/server/data/trials.json
   ```

7. **Set Environment Variables**
   - In WSGI config, set:
     - SECRET_KEY
     - ADMIN_PASSWORD
     - SMTP credentials
     - FLASK_ENV = 'production'

8. **Test Status Endpoint**
   ```bash
   curl https://wavyvoy.pythonanywhere.com/api/v1/status
   ```
   Expected: `{"status": "online", "version": "1.0.0"}`

9. **Test Login Endpoint**
   ```bash
   curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/license/validate \
     -H "Content-Type: application/json" \
     -d '{"email":"test@test.com","license_key":"TEST","hardware_id":"test","device_name":"test"}'
   ```

10. **Create Auto-Update Script** (optional)
    ```bash
    cat > ~/apps/update_from_github.sh << 'EOF'
    #!/bin/bash
    cd ~/apps/wbf
    source venv/bin/activate
    git pull origin master
    pip install -r server/requirements.txt
    echo "✅ Updated from GitHub"
    EOF
    chmod +x ~/apps/update_from_github.sh
    ```

---

## File References

### Documentation Files
- [PYTHONANYWHERE_GITHUB_SETUP.md](./PYTHONANYWHERE_GITHUB_SETUP.md) - Complete setup guide
- [PYTHONANYWHERE_DEPLOYMENT_CHECKLIST.md](./PYTHONANYWHERE_DEPLOYMENT_CHECKLIST.md) - Checklist
- [PRODUCTION_SERVER_COMMUNICATION_GUIDE.md](./PRODUCTION_SERVER_COMMUNICATION_GUIDE.md) - API documentation

### Key Code Files
- `server/api/routes.py` - API endpoints
- `server/services/license_manager.py` - License business logic
- `server/app.py` - Flask application
- `client/gui/login_window_new.py` - Login UI with server communication
- `client/config/config.py` - API endpoint configuration

---

## Important Notes

### Security
- **Never commit sensitive files to GitHub:**
  - ❌ licenses.json
  - ❌ trials.json
  - ❌ purchases.jsonl
  - ❌ .env files
  
- These are protected by .gitignore and created manually on PythonAnywhere

### Configuration
- **Update paths in WSGI config:**
  - Replace `/home/wavyvoy/` with your username
  - Template provided in PYTHONANYWHERE_GITHUB_SETUP.md

- **Environment variables critical:**
  - SECRET_KEY - Generate strong random string
  - SMTP credentials - For email notifications
  - ADMIN_PASSWORD - For admin operations

### Auto-Update
- Optional scheduled task can pull from GitHub daily
- Manual pull also available: `cd ~/apps/wbf && git pull origin master`
- Always reload web app after pulling new code

---

## Testing After Deployment

### From Client
```python
from client.config.config import VALIDATE_URL

# Should point to: https://wavyvoy.pythonanywhere.com/api/v1/license/validate
print(VALIDATE_URL)
```

### From Browser/Terminal
```bash
# Status
curl https://wavyvoy.pythonanywhere.com/api/v1/status

# License validation
curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/license/validate \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","license_key":"TEST","hardware_id":"test","device_name":"test"}'

# Forgot license
curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/license/forgot \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com"}'

# Trial eligibility
curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/trial/check-eligibility \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","hardware_id":"test123"}'
```

---

## Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| SSH key permission denied | Verify key added to GitHub: `ssh -T git@github.com` |
| Can't clone repository | Check SSH key setup in GitHub Settings |
| Import errors after git pull | Activate venv: `source ~/apps/wbf/venv/bin/activate` |
| Old code still showing | Click **Reload** in Web tab, wait 10 seconds |
| 500 errors on endpoints | Check error log in Web tab for Python tracebacks |
| Missing data files | Create manually: `mkdir -p ~/apps/wbf/server/data && echo '{}' > ~/.../licenses.json` |

---

## Next Steps

1. **Follow the deployment checklist** in PYTHONANYWHERE_DEPLOYMENT_CHECKLIST.md
2. **Use the setup guide** for detailed explanations in PYTHONANYWHERE_GITHUB_SETUP.md
3. **Test all endpoints** using the curl commands above
4. **Monitor logs** in PythonAnywhere Web tab
5. **Set up auto-updates** (optional) using the update script

---

## Useful PythonAnywhere Links

- **Bash Console:** https://www.pythonanywhere.com/consoles/
- **Web Apps:** https://www.pythonanywhere.com/web_app_setup/
- **Tasks:** https://www.pythonanywhere.com/tasks/
- **Error Logs:** Check in Web tab under your web app
- **Domains:** Manage at https://www.pythonanywhere.com/account/internet_domains/

---

## Support Resources

- **GitHub Repository:** https://github.com/voy-tech-voy/wbf
- **PythonAnywhere Docs:** https://help.pythonanywhere.com/
- **Flask Docs:** https://flask.palletsprojects.com/
- **Git Docs:** https://git-scm.com/doc

---

**Status:** ✅ Ready for Deployment  
**Date:** December 17, 2025  
**Version:** 1.0

Start with the **PYTHONANYWHERE_DEPLOYMENT_CHECKLIST.md** for phase-by-phase deployment!
