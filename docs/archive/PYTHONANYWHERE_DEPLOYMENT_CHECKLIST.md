# PythonAnywhere Deployment Checklist

**Date:** December 17, 2025  
**Goal:** Deploy ImgApp server to PythonAnywhere with GitHub integration

---

## Pre-Deployment (Local)

- [ ] All code committed and pushed to GitHub
- [ ] `.gitignore` properly configured (no sensitive files)
- [ ] Requirements file updated: `pip freeze > server/requirements.txt`
- [ ] Test locally that all endpoints work

**Commit to verify:**
```bash
git log --oneline -5
# Should show recent commits
```

---

## PythonAnywhere Setup (Step-by-Step)

### Phase 1: SSH & GitHub Connection

- [ ] **1.1** Open PythonAnywhere Bash Console
- [ ] **1.2** Generate SSH key: `ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""`
- [ ] **1.3** Copy public key: `cat ~/.ssh/id_rsa.pub`
- [ ] **2.1** Go to GitHub Settings → SSH and GPG keys
- [ ] **2.2** Add new SSH key (paste public key from step 1.3)
- [ ] **2.3** Test SSH: `ssh -T git@github.com`
  - Expected: `Hi voy-tech-voy! You've successfully authenticated...`

### Phase 2: Clone Repository

- [ ] **3.1** SSH to PythonAnywhere: `cd ~/apps`
- [ ] **3.2** Clone repo: `git clone git@github.com:voy-tech-voy/wbf.git`
- [ ] **3.3** Verify: `ls -la ~/apps/wbf/` (should show client/, server/, etc.)

### Phase 3: Virtual Environment

- [ ] **4.1** Create venv: `cd ~/apps/wbf && python3.10 -m venv venv`
- [ ] **4.2** Activate: `source venv/bin/activate`
- [ ] **4.3** Install requirements: `pip install -r server/requirements.txt`
- [ ] **4.4** Verify Flask: `pip list | grep Flask`

### Phase 4: Web App Configuration

- [ ] **5.1** Go to PythonAnywhere **Web** tab
- [ ] **5.2** Update WSGI configuration file with correct paths
  - Replace `/home/wavyvoy/` with your username
  - Verify project directory path
  - Verify virtual environment path
- [ ] **5.3** Click **Reload** button
- [ ] **5.4** Check for errors in error log

### Phase 5: Sensitive Data Setup

- [ ] **8.1** Create data directory: `mkdir -p ~/apps/wbf/server/data`
- [ ] **8.2** Create licenses.json: `echo '{}' > ~/apps/wbf/server/data/licenses.json`
- [ ] **8.3** Create trials.json: `echo '{}' > ~/apps/wbf/server/data/trials.json`
- [ ] **8.4** Set environment variables in WSGI config:
  - [ ] SECRET_KEY
  - [ ] ADMIN_PASSWORD
  - [ ] SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
  - [ ] FROM_EMAIL
  - [ ] FLASK_ENV = 'production'
- [ ] **8.5** Reload web app again

### Phase 6: Verification

- [ ] **9.1** Test status endpoint:
  ```bash
  curl https://wavyvoy.pythonanywhere.com/api/v1/status
  ```
  Expected: `{"status": "online", "version": "1.0.0"}`

- [ ] **9.2** Test license validation:
  ```bash
  curl -X POST https://wavyvoy.pythonanywhere.com/api/v1/license/validate \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","license_key":"TEST","hardware_id":"test","device_name":"test"}'
  ```
  Expected: Response (success or validation error, not 500)

- [ ] **9.3** Check error logs for Python errors
- [ ] **9.4** Check server logs for request logs

### Phase 7: Automation (Optional)

- [ ] **6.1** Create update script: `~/apps/update_from_github.sh`
- [ ] **6.2** Make executable: `chmod +x ~/apps/update_from_github.sh`
- [ ] **7.1** Set up scheduled task in PythonAnywhere **Tasks** tab
  - Command: `/home/wavyvoy/apps/update_from_github.sh`
  - Frequency: Daily (or as needed)

---

## Post-Deployment Testing

### Client-Side Testing

From your local machine (or emulator):

- [ ] **Login Test**
  - Email: test email
  - License: test license from database
  - Expected: Server validation succeeds and app opens

- [ ] **Trial Test**
  - Email: new email not in database
  - Expected: Trial license created and returned

- [ ] **Forgot License Test**
  - Email: existing email in database
  - Expected: License key retrieved and displayed

- [ ] **Connection Error Test**
  - Disconnect internet
  - Try login
  - Expected: Proper error message displayed

### Server-Side Testing

SSH to PythonAnywhere:

- [ ] Check error log for any Python errors
- [ ] Verify data files exist and are readable
- [ ] Test database files are being created/updated
- [ ] Monitor disk space usage

---

## Configuration Details

### WSGI File Location
```
PythonAnywhere Web tab → Click on web app → WSGI configuration file
```

### Environment Variables Location
```
Option 1: In WSGI file (recommended for sensitive data)
Option 2: PythonAnywhere Web tab → Environment variables section
```

### Important Paths (Replace `wavyvoy` with YOUR username)
- Project: `/home/wavyvoy/apps/wbf/`
- Venv: `/home/wavyvoy/apps/wbf/venv/`
- Data: `/home/wavyvoy/apps/wbf/server/data/`
- Logs: `/var/log/wavyvoy_pythonanywhere_com_*`

---

## Troubleshooting Quick Links

| Error | Solution |
|-------|----------|
| SSH key permission denied | Verify key added to GitHub + test `ssh -T git@github.com` |
| Module not found after git pull | Activate venv and re-run `pip install -r server/requirements.txt` |
| Old code still showing | Click **Reload** in Web tab and wait 10 seconds |
| 500 error on endpoints | Check error log in Web tab for Python exceptions |
| Can't find licenses.json | Create file: `echo '{}' > ~/apps/wbf/server/data/licenses.json` |
| Missing environment variables | Verify set in WSGI config or Environment variables section |

---

## Success Indicators

✅ Setup is complete when:

1. ✅ SSH connection to GitHub works
2. ✅ Repository cloned to `~/apps/wbf/`
3. ✅ Virtual environment created and dependencies installed
4. ✅ `/api/v1/status` endpoint returns `{"status": "online"}`
5. ✅ License validation endpoint accepts requests
6. ✅ No 500 errors in error log
7. ✅ Client can connect and login with real license
8. ✅ Trial creation works
9. ✅ Forgot license retrieval works
10. ✅ Auto-update script ready (if using scheduled tasks)

---

## After Deployment

### Regular Maintenance

- [ ] Monitor error logs weekly
- [ ] Check disk space monthly
- [ ] Update dependencies as needed
- [ ] Test one endpoint per week

### Code Updates

To deploy new code:

```bash
# Option 1: Manual pull
cd ~/apps/wbf && git pull origin master

# Option 2: Run update script
~/apps/update_from_github.sh

# Option 3: Automatic via scheduled task
# (Already set up in Phase 7)
```

Then reload the web app in PythonAnywhere dashboard.

---

## Contact & Support

**GitHub Repo:** https://github.com/voy-tech-voy/wbf  
**PythonAnywhere:** https://www.pythonanywhere.com  
**Last Setup Date:** December 17, 2025

---

**Ready to deploy? Start with Phase 1: SSH & GitHub Connection**
