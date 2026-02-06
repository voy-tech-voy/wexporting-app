"""
Trial Usage Manager

This module tracks file/batch usage counts for trial users.

NOTE: There are two trial-related systems:
1. TrialManager (this file) - Tracks usage counts (files processed) by hardware_id
2. LicenseManager.create_trial_license() - Creates time-limited trial license keys

They work together:
- LicenseManager creates trial licenses with expiry dates
- TrialManager enforces usage limits within those trials

Trial flow:
1. User requests trial → LicenseManager creates trial license (7 days)
2. User processes files → TrialManager tracks file count
3. Trial ends when: (a) time expires OR (b) file limit reached
"""

import json
import os
import threading
from datetime import datetime
from config.settings import Config

# Thread lock for file operations
_trial_usage_lock = threading.Lock()


class TrialManager:
    """Tracks trial usage counts (files processed) - works with LicenseManager's trial licenses"""
    
    def __init__(self):
        self.trials_file = Config.TRIALS_FILE
        self.rules_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'trial_rules.json')
        self.ensure_file()

    def load_rules(self):
        """Load trial rules (limits)"""
        try:
            if os.path.exists(self.rules_file):
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"max_batches": 10, "max_files": 30}

    def ensure_file(self):
        """Ensure trials file exists"""
        if not os.path.exists(self.trials_file):
            os.makedirs(os.path.dirname(self.trials_file), exist_ok=True)
            with open(self.trials_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def load_trials(self):
        """Load trials with thread safety"""
        with _trial_usage_lock:
            try:
                with open(self.trials_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    def save_trials(self, trials):
        """Save trials with thread safety and atomic write"""
        with _trial_usage_lock:
            try:
                temp_file = self.trials_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(trials, f, indent=2)
                os.replace(temp_file, self.trials_file)
                return True
            except Exception:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
                return False

    def check_trial(self, hardware_id):
        """Check trial usage for a hardware ID"""
        trials = self.load_trials()
        rules = self.load_rules()
        max_files = rules.get("max_files", 30)
        
        if hardware_id not in trials:
            return {
                "allowed": True, 
                "remaining_files": max_files,
                "files_used": 0
            }
        
        data = trials[hardware_id]
        files_used = data.get("files_used", 0)
        
        allowed = files_used < max_files
        
        return {
            "allowed": allowed,
            "remaining_files": max(0, max_files - files_used),
            "files_used": files_used,
            "limits": {"files": max_files}
        }

    def increment_trial(self, hardware_id, files_count=1):
        """Increment trial usage count"""
        trials = self.load_trials()
        rules = self.load_rules()
        max_files = rules.get("max_files", 30)
        now = datetime.utcnow().isoformat()
        
        if hardware_id not in trials:
            trials[hardware_id] = {
                "files_used": 0,
                "first_seen": now,
                "last_seen": now
            }
            
        data = trials[hardware_id]
        # Migrate legacy data if needed
        if "conversions_used" in data:
            if "files_used" not in data:
                data["files_used"] = 0
            del data["conversions_used"]
            
        data["last_seen"] = now
        
        if data["files_used"] < max_files:
            data["files_used"] = data.get("files_used", 0) + files_count
            self.save_trials(trials)
            
            return {
                "success": True, 
                "files_used": data["files_used"],
                "remaining_files": max(0, max_files - data["files_used"])
            }
        else:
            return {
                "success": False,
                "message": "Trial limit reached",
                "files_used": data.get("files_used", 0),
                "remaining_files": 0
            }

    def reset_trial(self, hardware_id):
        """Reset trial usage for a hardware ID (admin function)"""
        trials = self.load_trials()
        if hardware_id in trials:
            trials[hardware_id]["batches_used"] = 0
            trials[hardware_id]["files_used"] = 0
            if "conversions_used" in trials[hardware_id]:
                del trials[hardware_id]["conversions_used"]
            self.save_trials(trials)
            return {"success": True, "message": "Trial reset"}
        return {"success": False, "message": "Hardware ID not found"}
