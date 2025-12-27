import ctypes
from ctypes import wintypes
import logging
import time
import os

logger = logging.getLogger()

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

# Window Messages and Power Constants
HWND_BROADCAST = 0xFFFF
WM_SYSCOMMAND = 0x0112
SC_MONITORPOWER = 0xF170
MONITOR_OFF = 2
MONITOR_ON = -1

# Execution State Constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

# Power Request Constants
POWER_REQUEST_CONTEXT_VERSION = 0
POWER_REQUEST_CONTEXT_SIMPLE_STRING = 0x1
POWER_REQUEST_CONTEXT_DETAILED_STRING = 0x2

PowerRequestDisplayRequired = 0
PowerRequestSystemRequired = 1
PowerRequestAwayModeRequired = 2
PowerRequestExecutionRequired = 3

class REASON_CONTEXT(ctypes.Structure):
    class _Reason(ctypes.Union):
        class _Detailed(ctypes.Structure):
            _fields_ = [("LocalizedReasonModule", wintypes.LPCWSTR),
                        ("LocalizedReasonId", wintypes.ULONG),
                        ("ReasonStringCount", wintypes.ULONG),
                        ("ReasonStrings", ctypes.POINTER(wintypes.LPCWSTR))]
        _fields_ = [("Detailed", _Detailed),
                    ("SimpleReasonString", wintypes.LPCWSTR)]
    _fields_ = [("Version", wintypes.ULONG),
                ("Flags", wintypes.DWORD),
                ("Reason", _Reason)]

class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD),
                ("HighPart", wintypes.LONG)]

def enter_s0_and_wake(duration_seconds: int):
    # Use Task Scheduler to wake the system
    from util_task_scheduler import create_wake_task, delete_wake_task
    import sys
    
    task_name = "StressTestWakeTask"
    
    # Create a helper script that just prints "I am awake" and exits
    # This is what the scheduled task will run to wake the system
    helper_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wake_helper.py")
    with open(helper_script, "w") as f:
        f.write("import time; print('System Woken by Task Scheduler'); time.sleep(5)")
        
    logger.info(f"Scheduling task '{task_name}' to wake system in {duration_seconds} seconds...")
    if not create_wake_task(task_name, duration_seconds, helper_script):
        logger.error("Failed to schedule wake task.")
        return False

    logger.info(f"Enter S0 (Monitor OFF) for {duration_seconds}s...")
    
    # Turn Monitor OFF
    user32.PostMessageW(
        HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
    
    # Wait for the duration + buffer
    # We use a simple sleep here because the Task Scheduler will handle the waking
    # Even if this thread is suspended, the Task Scheduler will wake the system,
    # which will unsleep this thread eventually (or at least wake the hardware).
    time.sleep(duration_seconds + 5)
    
    logger.info("Sleep duration passed. Cleaning up...")
    
    # Turn Monitor ON
    user32.PostMessageW(
        HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON)
        
    # Force display on
    kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    )
    
    delete_wake_task(task_name)
    if os.path.exists(helper_script):
        os.remove(helper_script)
        
    return True

if __name__ == "__main__":
    from util_resources import enable_privilege
    from util_subprocess import enable_wake_timers

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    enable_privilege("SeWakeAlarmPrivilege")
    enable_wake_timers()
    enter_s0_and_wake(10)
