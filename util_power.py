import ctypes
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

def enter_s0_and_wake(duration_seconds: int):
    # Use Task Scheduler to wake the system
    from util_task_scheduler import create_wake_task, delete_wake_task
    import sys
    
    task_name = "StressTestWakeTask"
    
    # Use the standalone util_wakeup.py script
    # This script will be run by Task Scheduler, which has execution privileges during S0
    helper_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "util_wakeup.py")
    
    if not os.path.exists(helper_script):
        logger.error(f"Wakeup script not found: {helper_script}")
        return False
        
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
    
    # We will print a countdown to see exactly when the script stops running (suspends)
    start_time = time.time()
    wake_time = start_time + duration_seconds
    
    try:
        while time.time() < wake_time + 5: # Wait up to 5 seconds past wake time
            remaining = int(wake_time - time.time())
            if remaining > 0:
                print(f"Sleeping... {remaining}s remaining", end='\r')
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    print("\n") # Newline after countdown
    actual_wake_time = time.time()
    drift = actual_wake_time - wake_time
    
    if drift > 2:
        logger.warning(f"System woke up {drift:.2f}s LATE. (Hardware likely suspended)")
    else:
        logger.info(f"System woke up on time (Drift: {drift:.2f}s).")

    logger.info("Sleep duration passed. Cleaning up...")
    
    # Turn Monitor ON
    user32.PostMessageW(
        HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON)
        
    # Force display on
    kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    )
    
    delete_wake_task(task_name)
        
    return True

if __name__ == "__main__":
    from util_resources import enable_privilege
    from util_subprocess import enable_wake_timers

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    enable_privilege("SeWakeAlarmPrivilege")
    enable_wake_timers()
    enter_s0_and_wake(10)
