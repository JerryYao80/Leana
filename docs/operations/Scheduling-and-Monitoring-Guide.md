# Barra CNE5 Scheduling and Monitoring Guide

**Version**: 1.0
**Created**: 2026-02-06
**Purpose**: Guide for scheduling daily updates and monitoring system health

---

## 1. Daily Update Schedule

### 1.1 Recommended Schedule

```
02:00 - Tushare data download
02:30 - Incremental factor calculation
02:45 - Data quality validation
03:00 - System ready for trading
09:30 - Market opens
```

### 1.2 Cron Job Setup

**File**: `/etc/crontab`

```bash
# Barra CNE5 Daily Updates

# Download latest Tushare data at 2:00 AM
0 2 * * * /usr/bin/python3 /home/project/ccleana/Leana/scripts/tushare/download_daily_data.py >> /var/log/barra/download.log 2>&1

# Incremental factor calculation at 2:30 AM
30 2 * * * /usr/bin/python3 /home/project/ccleana/Leana/scripts/barra/step6_incremental_update.py >> /var/log/barra/update.log 2>&1

# Data quality validation at 2:45 AM
45 2 * * * /usr/bin/python3 /home/project/ccleana/Leana/scripts/barra/monitor_data_quality.py >> /var/log/barra/monitor.log 2>&1

# Monthly full recalculation (1st of month at 1:00 AM)
0 1 1 * * /home/project/ccleana/Leana/scripts/barra/run_full_pipeline.sh >> /var/log/barra/full_pipeline.log 2>&1

# Weekly backup (Sunday at 3:00 AM)
0 3 * * 0 /home/project/ccleana/Leana/scripts/barra/backup_factor_data.sh >> /var/log/barra/backup.log 2>&1
```

### 1.3 Installation

```bash
# Create log directory
sudo mkdir -p /var/log/barra
sudo chown $USER:$USER /var/log/barra

# Install cron jobs
sudo crontab -e
# Paste the cron entries above

# Verify cron jobs
crontab -l | grep barra
```

---

## 2. Monitoring Scripts

### 2.1 Data Quality Monitor

**File**: `scripts/barra/monitor_data_quality.py`

```python
#!/usr/bin/env python3
"""
Monitor Barra factor data quality and send alerts if issues detected.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText


def check_latest_factors():
    """Check if latest factor data is available and valid."""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # Check if yesterday's factors exist (accounting for weekends)
    for days_back in range(1, 5):
        check_date = today - timedelta(days=days_back)
        factor_file = Path(f"/home/project/ccleana/data/barra_factors/by_date/{check_date.strftime('%Y%m%d')}.parquet")

        if factor_file.exists():
            print(f"✓ Found factors for {check_date}")

            # Validate factor quality
            df = pd.read_parquet(factor_file)

            # Check 1: Stock coverage
            if len(df) < 4000:
                send_alert(f"WARNING: Low stock coverage on {check_date}: {len(df)} stocks")

            # Check 2: Factor variance
            for factor in ['growth', 'leverage']:
                variance = df[factor].var()
                if variance < 0.001:
                    send_alert(f"WARNING: {factor} has zero variance on {check_date}")

            # Check 3: Missing values
            missing_pct = df.isnull().mean()
            for factor, pct in missing_pct.items():
                if pct > 0.2:
                    send_alert(f"WARNING: {factor} has {pct:.1%} missing values on {check_date}")

            return True

    # No recent factors found
    send_alert(f"ERROR: No factor data found for past 4 days")
    return False


def send_alert(message):
    """Send alert via email or logging."""
    print(f"ALERT: {message}")

    # TODO: Implement email alerts
    # smtp_server = "smtp.gmail.com"
    # sender = "alerts@example.com"
    # recipient = "admin@example.com"
    # msg = MIMEText(message)
    # msg['Subject'] = "Barra CNE5 Alert"
    # msg['From'] = sender
    # msg['To'] = recipient
    # with smtplib.SMTP(smtp_server, 587) as server:
    #     server.starttls()
    #     server.login(sender, "password")
    #     server.send_message(msg)


if __name__ == "__main__":
    check_latest_factors()
```

### 2.2 System Health Check

**File**: `scripts/barra/health_check.sh`

```bash
#!/bin/bash
# Comprehensive system health check

echo "=== Barra CNE5 System Health Check ==="
echo "Time: $(date)"
echo ""

# Check 1: Disk space
echo "[1] Disk Space"
df -h /home/project/ccleana/data | tail -1
DISK_USAGE=$(df /home/project/ccleana/data | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "WARNING: Disk usage above 80%"
fi
echo ""

# Check 2: Latest factor data
echo "[2] Latest Factor Data"
LATEST_FILE=$(ls -t /home/project/ccleana/data/barra_factors/by_date/*.parquet | head -1)
if [ -n "$LATEST_FILE" ]; then
    echo "Latest: $(basename $LATEST_FILE)"
    echo "Size: $(du -h $LATEST_FILE | cut -f1)"
else
    echo "ERROR: No factor files found"
fi
echo ""

# Check 3: Cron jobs
echo "[3] Cron Jobs Status"
crontab -l | grep barra | wc -l | xargs echo "Active cron jobs:"
echo ""

# Check 4: Recent logs
echo "[4] Recent Errors in Logs"
if [ -f /var/log/barra/update.log ]; then
    grep -i error /var/log/barra/update.log | tail -5
else
    echo "No error logs found"
fi
echo ""

# Check 5: Process status
echo "[5] Running Processes"
ps aux | grep -E "step[0-9]|barra" | grep -v grep
echo ""

echo "=== Health Check Complete ==="
```

### 2.3 Performance Monitor

**File**: `scripts/barra/monitor_performance.py`

```python
#!/usr/bin/env python3
"""
Monitor Barra system performance metrics.
"""

import time
import psutil
from pathlib import Path


def monitor_update_performance():
    """Monitor incremental update performance."""
    log_file = Path("/var/log/barra/update.log")

    if not log_file.exists():
        print("No update log found")
        return

    # Parse log for timing information
    with open(log_file, 'r') as f:
        lines = f.readlines()

    # Extract timing info
    start_time = None
    end_time = None

    for line in lines:
        if "Incremental update complete" in line:
            # Extract timestamp
            timestamp_str = line.split(' - ')[0]
            end_time = timestamp_str

    if end_time:
        print(f"Last update completed at: {end_time}")
    else:
        print("No completed updates found in log")


def monitor_system_resources():
    """Monitor system resource usage."""
    print("=== System Resources ===")

    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"CPU Usage: {cpu_percent}%")

    # Memory usage
    memory = psutil.virtual_memory()
    print(f"Memory Usage: {memory.percent}% ({memory.used / 1e9:.1f}GB / {memory.total / 1e9:.1f}GB)")

    # Disk usage
    disk = psutil.disk_usage('/home/project/ccleana/data')
    print(f"Disk Usage: {disk.percent}% ({disk.used / 1e9:.1f}GB / {disk.total / 1e9:.1f}GB)")

    # Disk I/O
    disk_io = psutil.disk_io_counters()
    print(f"Disk Read: {disk_io.read_bytes / 1e9:.1f}GB")
    print(f"Disk Write: {disk_io.write_bytes / 1e9:.1f}GB")


if __name__ == "__main__":
    monitor_update_performance()
    print()
    monitor_system_resources()
```

---

## 3. Alerting

### 3.1 Alert Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| No factor data for 2+ days | Critical | Email + SMS |
| Disk usage > 90% | Critical | Email + SMS |
| Factor variance = 0 | High | Email |
| Stock coverage < 4000 | Medium | Email |
| Update time > 5 minutes | Low | Log only |

### 3.2 Email Alerts Setup

**File**: `scripts/barra/alert_config.json`

```json
{
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "sender_email": "alerts@example.com",
  "sender_password": "your_password",
  "recipients": [
    "admin@example.com",
    "trader@example.com"
  ],
  "alert_levels": {
    "critical": ["email", "sms"],
    "high": ["email"],
    "medium": ["email"],
    "low": ["log"]
  }
}
```

### 3.3 SMS Alerts (Optional)

```python
# Using Twilio for SMS alerts
from twilio.rest import Client

def send_sms_alert(message):
    """Send SMS alert via Twilio."""
    account_sid = "your_account_sid"
    auth_token = "your_auth_token"
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        body=message,
        from_="+1234567890",
        to="+0987654321"
    )

    print(f"SMS sent: {message.sid}")
```

---

## 4. Backup Strategy

### 4.1 Backup Script

**File**: `scripts/barra/backup_factor_data.sh`

```bash
#!/bin/bash
# Backup Barra factor data

BACKUP_DIR="/backup/barra"
DATE=$(date +%Y%m%d)
SOURCE_DIR="/home/project/ccleana/data/barra_factors"

echo "Starting backup at $(date)"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup factor data
tar -czf $BACKUP_DIR/barra_factors_$DATE.tar.gz $SOURCE_DIR/by_date

# Backup risk parameters
cp /home/project/ccleana/data/barra_risk/risk_params_latest.json $BACKUP_DIR/risk_params_$DATE.json

# Remove backups older than 30 days
find $BACKUP_DIR -name "barra_factors_*.tar.gz" -mtime +30 -delete

echo "Backup complete at $(date)"
```

### 4.2 Restore Procedure

```bash
#!/bin/bash
# Restore from backup

BACKUP_FILE="/backup/barra/barra_factors_20240101.tar.gz"
RESTORE_DIR="/home/project/ccleana/data/barra_factors"

# Extract backup
tar -xzf $BACKUP_FILE -C $RESTORE_DIR

echo "Restore complete"
```

---

## 5. Troubleshooting

### 5.1 Common Issues

#### Issue 1: Cron job not running

**Symptoms**: No new factor files generated

**Diagnosis**:
```bash
# Check cron service
systemctl status cron

# Check cron logs
grep CRON /var/log/syslog | tail -20

# Test cron job manually
/usr/bin/python3 /home/project/ccleana/Leana/scripts/barra/step6_incremental_update.py
```

**Solution**:
```bash
# Restart cron service
sudo systemctl restart cron

# Verify cron jobs
crontab -l
```

#### Issue 2: Incremental update fails

**Symptoms**: Error in update.log

**Diagnosis**:
```bash
# Check error logs
tail -50 /var/log/barra/update.log | grep ERROR

# Check disk space
df -h /home/project/ccleana/data

# Check file permissions
ls -la /home/project/ccleana/data/barra_factors/by_date/
```

**Solution**:
```bash
# Run with verbose logging
python3 scripts/barra/step6_incremental_update.py --verbose

# If disk full, clean up old files
find /home/project/ccleana/data/barra_factors/by_date -name "*.parquet" -mtime +365 -delete
```

#### Issue 3: Data quality alerts

**Symptoms**: Alerts about zero variance or missing data

**Diagnosis**:
```bash
# Check specific date
python3 << EOF
import pandas as pd
df = pd.read_parquet('/home/project/ccleana/data/barra_factors/by_date/20240101.parquet')
print(df.describe())
print(df.isnull().sum())
EOF
```

**Solution**:
```bash
# Re-run full pipeline for affected dates
python3 scripts/barra/step1_calculate_factors.py --start-date 20240101 --end-date 20240101
```

---

## 6. Performance Optimization

### 6.1 Incremental Update Optimization

**Current**: ~2 minutes for 1 day
**Target**: <1 minute

**Optimizations**:
1. Use multiprocessing for stock calculations
2. Cache benchmark data
3. Use faster Parquet compression (snappy vs gzip)
4. Optimize factor calculations

### 6.2 Monitoring Dashboard

**Tools**: Grafana + Prometheus

**Metrics to track**:
- Update duration
- Factor coverage
- Data quality scores
- System resource usage
- Error rates

---

## 7. Maintenance Schedule

### 7.1 Daily Tasks

- ✅ Verify incremental update completed
- ✅ Check data quality alerts
- ✅ Monitor system resources

### 7.2 Weekly Tasks

- ✅ Review error logs
- ✅ Backup factor data
- ✅ Check disk space trends

### 7.3 Monthly Tasks

- ✅ Run full pipeline recalculation
- ✅ Review performance metrics
- ✅ Update documentation
- ✅ Test backup restore procedure

### 7.4 Quarterly Tasks

- ✅ Review and update factor weights
- ✅ Audit data quality
- ✅ Performance tuning
- ✅ Security updates

---

## 8. Runbook

### 8.1 Daily Operations

**Morning Checklist** (before market open):
```bash
# 1. Check system health
./scripts/barra/health_check.sh

# 2. Verify latest factors
ls -lh /home/project/ccleana/data/barra_factors/by_date/ | tail -5

# 3. Check for alerts
tail -20 /var/log/barra/monitor.log

# 4. Review update log
tail -50 /var/log/barra/update.log
```

### 8.2 Emergency Procedures

**If incremental update fails**:
1. Check error logs
2. Verify Tushare data availability
3. Run manual update with --verbose
4. If still failing, use previous day's factors
5. Escalate to development team

**If system is down**:
1. Check system resources (CPU, memory, disk)
2. Restart services if needed
3. Restore from backup if data corrupted
4. Document incident

---

## 9. Contact Information

**System Administrator**: admin@example.com
**Development Team**: dev@example.com
**Emergency Hotline**: +86-xxx-xxxx-xxxx

**Escalation Path**:
1. Level 1: System Administrator (response time: 1 hour)
2. Level 2: Development Team (response time: 4 hours)
3. Level 3: CTO (response time: 24 hours)

---

**Document Status**: ✅ Complete
**Version**: 1.0
**Last Updated**: 2026-02-06
**Next Review**: 2026-03-06
