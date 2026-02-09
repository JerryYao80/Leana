# Offline-Online Integration Guide

**Version**: 1.0
**Created**: 2026-02-06
**Purpose**: Guide for integrating offline Barra factor calculation with online LEAN backtesting

---

## Overview

This guide explains how the offline factor calculation pipeline feeds data into the LEAN algorithmic trading framework for backtesting and live trading.

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OFFLINE SYSTEM                            │
│  Tushare Data → Python Scripts → Factor Files (Parquet)     │
│  Runs: Daily 2AM (incremental) or Monthly (full)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Shared File System
                       │ /data/barra_factors/
                       │ /data/barra_risk/
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    ONLINE SYSTEM                             │
│  LEAN Framework → Load Factors → Backtest/Live Trade        │
│  Runs: On-demand (backtest) or Continuous (live)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Data Flow

### 1.1 Offline → Online Pipeline

```mermaid
graph LR
    A[Tushare API] -->|Download| B[Raw Data]
    B -->|step1-5| C[Factor Files]
    C -->|File System| D[LEAN Algorithm]
    D -->|Initialize| E[Load into Memory]
    E -->|OnData| F[Generate Insights]
    F -->|Portfolio| G[Place Orders]
```

### 1.2 Daily Update Cycle

```
02:00 - Tushare data download
02:30 - Incremental factor calculation (step6)
02:45 - Data quality validation
03:00 - Factors ready for use
09:30 - Market opens, live trading begins
```

---

## 2. Data Format Specifications

### 2.1 Factor Data (by_date)

**Location**: `/data/barra_factors/by_date/{YYYYMMDD}.parquet`

**Schema**:
```python
{
    'ts_code': str,           # '000001.SZ'
    'size': float,            # ln(market_cap)
    'beta': float,            # [-2, 3]
    'momentum': float,        # [-0.8, 2.0]
    'volatility': float,      # [0.01, 0.15]
    'non_linear_size': float, # size³
    'book_to_price': float,   # [0, 10]
    'liquidity': float,       # [0, 100]
    'earnings_yield': float,  # [-0.5, 0.5]
    'growth': float,          # [-0.5, 1.0]
    'leverage': float,        # [0, 1]
    'ind_*': int,             # 30 industry dummies (0 or 1)
}
```

**Example**:
```python
import pandas as pd
df = pd.read_parquet('/data/barra_factors/by_date/20240101.parquet')
print(df.head())

#     ts_code    size   beta  momentum  ...  ind_banking
# 0  000001.SZ  10.23   1.15     0.12  ...            1
# 1  000002.SZ   9.87   0.98    -0.05  ...            0
```

### 2.2 Risk Parameters

**Location**: `/data/barra_risk/risk_params_latest.json`

**Schema**:
```json
{
  "factor_covariance": {
    "size": {"size": 0.0012, "beta": 0.0003, ...},
    "beta": {"size": 0.0003, "beta": 0.0025, ...}
  },
  "estimation_date": "20241231",
  "half_life_days": 90,
  "num_observations": 252
}
```

### 2.3 Specific Risks

**Location**: `/data/barra_risk/specific_risks.parquet`

**Schema**:
```python
{
    'ts_code': str,
    'specific_risk': float,  # Annualized volatility
    'estimation_date': str
}
```

---

## 3. LEAN Integration

### 3.1 Loading Factor Data

**In BarraCNE5Algorithm.Initialize()**:

```python
def _load_factor_data(self) -> Dict:
    """Load all factor data into memory"""
    import glob
    import pandas as pd
    from datetime import datetime

    factor_data = {}
    factor_dir = "/data/barra_factors/by_date"

    for file_path in glob.glob(f"{factor_dir}/*.parquet"):
        # Extract date from filename
        filename = os.path.basename(file_path)
        date_str = filename.replace('.parquet', '')
        date = datetime.strptime(date_str, '%Y%m%d').date()

        # Load factor data
        df = pd.read_parquet(file_path)

        # Convert to dict for fast lookup
        factor_data[date] = df.set_index('ts_code').to_dict('index')

    self.Log(f"Loaded factors for {len(factor_data)} dates")
    return factor_data
```

**Memory Usage**: ~1.6GB for 6,552 trading days

### 3.2 Accessing Factors in OnData()

```python
def OnData(self, data):
    """Called every trading day"""
    current_date = self.Time.date()

    # Get factors for current date
    if current_date not in self.factor_data:
        self.Log(f"No factors available for {current_date}")
        return

    factors_today = self.factor_data[current_date]

    # Access factor for specific stock
    symbol = self.Symbol("000001.SZ")
    ts_code = symbol.Value

    if ts_code in factors_today:
        stock_factors = factors_today[ts_code]
        momentum = stock_factors['momentum']
        value = stock_factors['book_to_price']
        # ... use factors for alpha generation
```

### 3.3 Error Handling

```python
def _get_factor_safely(self, ts_code, factor_name, default=0.0):
    """Safely get factor value with fallback"""
    current_date = self.Time.date()

    try:
        return self.factor_data[current_date][ts_code][factor_name]
    except KeyError:
        self.Log(f"Missing {factor_name} for {ts_code} on {current_date}")
        return default
```

---

## 4. Scheduling

### 4.1 Cron Job Setup

**File**: `/etc/crontab`

```bash
# Daily data update at 2:00 AM
0 2 * * * /usr/bin/python3 /home/project/ccleana/Leana/scripts/tushare/download_daily_data.py

# Incremental factor calculation at 2:30 AM
30 2 * * * /usr/bin/python3 /home/project/ccleana/Leana/scripts/barra/step6_incremental_update.py

# Data quality validation at 2:45 AM
45 2 * * * /usr/bin/python3 /home/project/ccleana/Leana/scripts/barra/monitor_data_quality.py

# Monthly full recalculation (1st of month at 1:00 AM)
0 1 1 * * /home/project/ccleana/Leana/scripts/barra/run_full_pipeline.sh
```

### 4.2 Monitoring Script

**File**: `scripts/barra/monitor_data_quality.py`

```python
#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

def check_latest_factors():
    """Verify latest factor data is available"""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # Check if yesterday's factors exist
    factor_file = Path(f"/data/barra_factors/by_date/{yesterday.strftime('%Y%m%d')}.parquet")

    if not factor_file.exists():
        send_alert(f"Missing factors for {yesterday}")
        return False

    # Check factor quality
    df = pd.read_parquet(factor_file)

    # Check coverage
    if len(df) < 4000:
        send_alert(f"Low stock coverage: {len(df)} stocks")

    # Check for zero variance
    for factor in ['growth', 'leverage']:
        if df[factor].var() < 0.001:
            send_alert(f"{factor} has zero variance")

    return True

if __name__ == "__main__":
    check_latest_factors()
```

---

## 5. Troubleshooting

### 5.1 Common Issues

#### Issue 1: Missing Factor Files

**Symptom**: LEAN logs "No factors available for {date}"

**Causes**:
- Offline script failed to run
- File permissions issue
- Disk full

**Solution**:
```bash
# Check if files exist
ls -lh /data/barra_factors/by_date/ | tail -10

# Check disk space
df -h /data

# Re-run incremental update
python scripts/barra/step6_incremental_update.py
```

#### Issue 2: Memory Overflow

**Symptom**: LEAN crashes with OutOfMemoryException

**Causes**:
- Too many factor files loaded
- Memory leak

**Solution**:
```python
# Option 1: Load only date range needed
def _load_factor_data(self, start_date, end_date):
    factor_data = {}
    for date in pd.date_range(start_date, end_date):
        file_path = f"/data/barra_factors/by_date/{date.strftime('%Y%m%d')}.parquet"
        if Path(file_path).exists():
            df = pd.read_parquet(file_path)
            factor_data[date.date()] = df.set_index('ts_code').to_dict('index')
    return factor_data

# Option 2: Use memory-mapped files
df = pd.read_parquet(file_path, memory_map=True)
```

#### Issue 3: Stale Data

**Symptom**: Factors not updating daily

**Causes**:
- Cron job not running
- Tushare API failure
- Script error

**Solution**:
```bash
# Check cron job status
systemctl status cron

# Check cron logs
grep CRON /var/log/syslog | tail -20

# Manually run update
python scripts/barra/step6_incremental_update.py --verbose
```

### 5.2 Data Validation Checklist

Before running backtest:

- [ ] Factor files exist for all dates in backtest range
- [ ] No missing values >10% for any factor
- [ ] Factor variance >0.001 for all factors
- [ ] Risk parameters file exists and is recent
- [ ] File sizes are reasonable (~250KB per date file)

**Validation Script**:
```bash
#!/bin/bash
# scripts/barra/validate_before_backtest.sh

START_DATE="20200101"
END_DATE="20241231"

echo "Validating factor data from $START_DATE to $END_DATE..."

python3 << EOF
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

start = datetime.strptime('$START_DATE', '%Y%m%d')
end = datetime.strptime('$END_DATE', '%Y%m%d')

missing_dates = []
for date in pd.date_range(start, end):
    file_path = Path(f"/data/barra_factors/by_date/{date.strftime('%Y%m%d')}.parquet")
    if not file_path.exists():
        missing_dates.append(date)

if missing_dates:
    print(f"ERROR: Missing {len(missing_dates)} dates")
    for date in missing_dates[:10]:
        print(f"  - {date.strftime('%Y-%m-%d')}")
else:
    print("✓ All dates present")
EOF
```

---

## 6. Performance Optimization

### 6.1 Offline Calculation

**Current Performance**:
- Full pipeline: 36 minutes
- Incremental update: <2 minutes

**Optimization Tips**:

1. **Increase Parallelism**:
```bash
# Use more workers (if CPU allows)
python scripts/barra/step1_calculate_factors.py --parallel 8
# 18 min → 10 min
```

2. **Use SSD Storage**:
```bash
# Move data to SSD
mv /data/barra_factors /mnt/ssd/barra_factors
ln -s /mnt/ssd/barra_factors /data/barra_factors
# 3 min → 1 min for step2
```

3. **Optimize Parquet Compression**:
```python
# In step1_calculate_factors.py
result.to_parquet(output_path, compression='snappy', index=False)
# Faster than default 'gzip'
```

### 6.2 LEAN Backtest

**Current Performance**:
- 10-year backtest: 15 minutes

**Optimization Tips**:

1. **Reduce Logging**:
```python
# In BarraCNE5Algorithm
self.SetLogLevel(LogLevel.Error)  # Only log errors
```

2. **Limit Universe Size**:
```python
# Trade only CSI300 instead of all stocks
def _select_universe(self, fundamental):
    return [x for x in fundamental if x.Symbol in self.csi300_symbols]
```

3. **Use Coarse Universe Selection**:
```python
# Filter before loading detailed data
self.AddUniverse(self.CoarseSelectionFunction)
```

---

## 7. Best Practices

### 7.1 Data Management

1. **Backup Strategy**:
```bash
# Daily backup of factor data
rsync -av /data/barra_factors/ /backup/barra_factors_$(date +%Y%m%d)/
```

2. **Retention Policy**:
- Keep daily factors for 10 years
- Archive older data to cold storage
- Delete intermediate files after validation

3. **Version Control**:
```bash
# Tag factor data versions
echo "v1.0.0" > /data/barra_factors/VERSION
git tag -a factor-data-v1.0.0 -m "Initial factor data release"
```

### 7.2 Code Organization

```
/home/project/ccleana/Leana/
├── scripts/barra/              # Offline calculation
│   ├── step1_calculate_factors.py
│   ├── step2_transpose_factors.py
│   ├── step3_factor_returns.py
│   ├── step4_risk_model.py
│   ├── step5_validate.py
│   └── step6_incremental_update.py
├── Algorithm.Python/           # LEAN algorithms
│   ├── BarraCNE5Algorithm.py
│   └── BarraAlphaModel.py
├── config/                     # Configuration
│   ├── factor_weights.json
│   └── config-barra-cne5-backtest.json
└── docs/design/                # Documentation
    ├── Barra-CNE5-System-Design-v4.md
    └── Offline-Online-Integration-Guide.md
```

### 7.3 Testing

1. **Unit Tests**:
```python
# tests/test_integration.py
def test_factor_loading():
    """Test LEAN can load factor data"""
    algorithm = BarraCNE5Algorithm()
    algorithm.Initialize()
    assert len(algorithm.factor_data) > 0
```

2. **Integration Tests**:
```bash
# Run mini backtest (1 month)
dotnet run --project Launcher/QuantConnect.Lean.Launcher.csproj \
  --config config/config-barra-cne5-test.json
```

3. **Smoke Tests**:
```bash
# Verify pipeline produces valid output
python scripts/barra/step1_calculate_factors.py --test-mode
```

---

## 8. Migration Guide

### 8.1 From v3 to v4

**Changes**:
1. Growth factor: 0.0 → Calculated from income data
2. Leverage factor: 0.5 → Calculated from fina_indicator
3. New script: step6_incremental_update.py

**Migration Steps**:

1. **Download Financial Data**:
```bash
python scripts/tushare/download_financial_data.py
```

2. **Re-run Full Pipeline**:
```bash
python scripts/barra/step1_calculate_factors.py --parallel 4
python scripts/barra/step2_transpose_factors.py
python scripts/barra/step3_factor_returns.py --parallel 4
python scripts/barra/step4_risk_model.py
python scripts/barra/step5_validate.py
```

3. **Verify Factor Quality**:
```bash
# Check validation report
open /data/barra_reports/validation_report.html

# Verify Growth and Leverage have non-zero variance
python -c "
import pandas as pd
df = pd.read_parquet('/data/barra_factors/by_date/20240101.parquet')
print(f'Growth variance: {df[\"growth\"].var():.4f}')
print(f'Leverage variance: {df[\"leverage\"].var():.4f}')
"
```

4. **Update LEAN Algorithm**:
```python
# No changes needed - algorithm automatically uses new factors
```

---

## 9. FAQ

**Q: How often should I run full recalculation?**
A: Monthly is recommended. Incremental updates are sufficient for daily use.

**Q: What if Tushare API is down?**
A: Use cached data from previous day. Set up backup data source (e.g., AkShare).

**Q: Can I run backtest while incremental update is running?**
A: Yes, but use a copy of factor data to avoid race conditions.

**Q: How do I add a new factor?**
A: See "Extensibility" section in System Design v4 document.

**Q: What's the minimum disk space needed?**
A: 20GB (10GB Tushare data + 2GB factors + 8GB buffer).

**Q: Can I use this for live trading?**
A: Yes, but add real-time data feed and order management system.

---

## 10. Support

**Documentation**:
- System Design v4: `docs/design/Barra-CNE5-System-Design-v4.md`
- Scripts Assessment: `docs/design/Barra-Scripts-Assessment.md`
- Data Mapping: `docs/design/Barra-CNE5-Data-Mapping.md`

**Logs**:
- Offline scripts: `/data/barra_reports/step*.log`
- LEAN backtest: `Launcher/bin/Debug/log.txt`

**Contact**:
- GitHub Issues: https://github.com/QuantConnect/Lean/issues
- LEAN Forum: https://www.quantconnect.com/forum

---

**Document Status**: ✅ Complete
**Version**: 1.0
**Last Updated**: 2026-02-06
**Next Review**: 2026-03-06
