#!/bin/bash
# Automated backup script for PythonAnywhere
# Schedule this in PythonAnywhere Tasks tab to run every 6 hours

cd /home/wavyvoy/apps/wbf
source venv/bin/activate

# Run hourly backup
python -c "
from server.services.backup_manager import run_scheduled_backup
import sys

try:
    result = run_scheduled_backup('hourly')
    if result:
        print('✅ Backup completed successfully')
        sys.exit(0)
    else:
        print('❌ Backup failed')
        sys.exit(1)
except Exception as e:
    print(f'❌ Backup error: {e}')
    sys.exit(1)
" >> /home/wavyvoy/logs/backup.log 2>&1

echo "Backup run at $(date)" >> /home/wavyvoy/logs/backup.log
