# S0 Modern Standby Service-Based Wake

## Overview

This implementation provides **fully automatic** S0 Modern Standby wake functionality using a Windows Service architecture. Unlike the previous implementation, **no manual user input is required** after the wake timer triggers.

## Architecture

```
┌─────────────────────────────────────────┐
│  Your Application (stress_test.py)     │
│  calls: enter_s0_with_service(10)      │
└──────────────┬──────────────────────────┘
               │ API Call
┌──────────────▼──────────────────────────┐
│  util_power.py                          │
│  - Lazy service installation            │
│  - Schedule wake via power.json         │
│  - Monitor wake completion              │
└──────────────┬──────────────────────────┘
               │ power.json
┌──────────────▼──────────────────────────┐
│  StressTestWakeService (Session 0)      │
│  - Monitors power.json for requests     │
│  - Creates Task Scheduler wake tasks    │
│  - Survives S0 sleep (not suspended)    │
│  - Logs wake history                    │
└──────────────┬──────────────────────────┘
               │ Task Scheduler
┌──────────────▼──────────────────────────┐
│  Wake Timer (RTC Alarm)                 │
│  - Wakes hardware from S0               │
│  - Runs wake_handler.py                 │
└──────────────┬──────────────────────────┘
               │ Display Wake
┌──────────────▼──────────────────────────┐
│  wake_handler.py                        │
│  - Forces monitor ON                    │
│  - Simulates mouse input                │
│  - Logs completion to power.json        │
└─────────────────────────────────────────┘
```

## Key Components

### 1. Windows Service (`service/wake_service.py`)
- Runs continuously in Session 0 (system services)
- **Not suspended** by Desktop Activity Moderator during S0
- Monitors `power.json` for wake schedule requests
- Creates Task Scheduler tasks with RTC wake timers
- Processes wake completions and maintains history

### 2. API (`util_power.py`)
**New Function:**
```python
def enter_s0_with_service(duration_seconds: int) -> bool:
    """
    Enter S0 Modern Standby with automatic wake.
    
    - Auto-installs service if not present
    - Schedules wake timer
    - Enters S0 sleep
    - Automatically wakes without user input
    - Returns after wake completes
    """
```

**Legacy Function (kept for compatibility):**
```python
def enter_s0_and_wake(duration_seconds: int) -> bool:
    """
    Original implementation - requires manual keypress after wake timer.
    """
```

### 3. Wake Handler (`service/wake_handler.py`)
- Executed by Task Scheduler when wake timer triggers
- Forces display wake (monitor ON, mouse simulation)
- Logs completion data to `wake_complete.json`
- Service reads this to confirm wake

### 4. State Management (`data/power.json`)
Single JSON file contains:
- `service_config`: Service configuration
- `current_state`: Current service state
- `wake_schedule`: Pending wake request (cleared after completion)
- `wake_history`: Array of completed wake events

## Usage

### Basic Usage (Recommended)

```python
from util_power import enter_s0_with_service

# Enter S0 for 10 seconds, auto-wake
success = enter_s0_with_service(10)
```

That's it! The function will:
1. Auto-install service if not present
2. Enter S0 Modern Standby
3. Wake automatically after 10 seconds
4. Return control to your script

### Manual Service Management (Optional)

```bash
# Install service
python service/wake_service_install.py install

# Check status
python service/wake_service_install.py status

# Stop service
python service/wake_service_install.py stop

# Remove service
python service/wake_service_install.py remove
```

### Demo Script

```bash
# Run demo (requires admin privileges)
python demo_service_wake.py
```

## Requirements

- **Windows 10/11** with Modern Standby support
- **Administrator privileges** (for service installation)
- **Python packages:** pywin32

## Error Handling

The API includes robust error handling:

1. **Service Installation Failure**
   - Falls back to legacy `enter_s0_and_wake()` method
   - Logs error details

2. **Wake Timeout**
   - Waits for wake completion with 60-second timeout
   - Forces manual display wake if timeout reached
   - Returns False but ensures display is restored

3. **Service Communication Failure**
   - Falls back to legacy method
   - Continues operation without service

## Files

```
stress_test/
├── util_power.py                   # Main API
├── demo_service_wake.py            # Demo script
├── service/
│   ├── wake_service.py             # Windows Service
│   ├── wake_handler.py             # Wake action script
│   └── wake_service_install.py     # Service installer
├── data/
│   ├── power.json                  # State management
│   └── wake_complete.json          # Temp completion data
└── log/
    └── wake_service.log            # Service logs
```

## Comparison: Service vs Legacy

| Feature | Service-Based | Legacy |
|---------|--------------|--------|
| Auto-wake | ✓ Yes | ✗ Requires keypress |
| Service install | Auto (lazy) | N/A |
| User input | None | Manual keypress |
| Reliability | High | Medium |
| Complexity | Medium | Low |
| S0 Compatible | ✓ Yes | ✓ Yes |

## How It Solves the Wake Problem

**The Problem:**
- Desktop applications are suspended by DAM during Modern Standby
- Wake timers wake hardware but not suspended processes
- Original Python script stayed suspended until manual user input

**The Solution:**
1. **Service in Session 0** - not suspended like desktop apps
2. **Task Scheduler integration** - creates tasks the service can respond to
3. **State file communication** - service and API communicate via power.json
4. **Separate wake handler** - fresh process runs on wake, not suspended
5. **Timeout with fallback** - ensures script always resumes

## Troubleshooting

**Service won't start:**
```bash
# Check if installed
sc query StressTestWakeService

# View service log
type log\wake_service.log
```

**Wake doesn't occur:**
- Check `log/wake_service.log` for errors
- Verify Task Scheduler task was created
- Check `data/power.json` for wake_schedule entry

**Permission errors:**
- Ensure running with administrator privileges
- Service installation requires admin rights

## Notes

- **S0 Modern Standby maintained** - does not force S3 sleep
- **Service runs continuously** - minimal memory overhead (~10MB)
- **State persists** - survives system reboots
- **History tracked** - wake_history shows all completed wakes
- **Production ready** - includes error handling and fallbacks
