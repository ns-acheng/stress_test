import ctypes
import logging
import time
import os
import json
import subprocess
import sys
from datetime import datetime

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

# Service configuration
SERVICE_NAME = "StressTestWakeService"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
SERVICE_DIR = os.path.join(BASE_DIR, 'service')
POWER_JSON = os.path.join(DATA_DIR, 'power.json')


def _ensure_data_dir():
    """Ensure data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_power_json():
    """Read power.json safely."""
    try:
        if os.path.exists(POWER_JSON):
            with open(POWER_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error reading power.json: {e}")
    return None


def _write_power_json(data):
    """Write power.json safely."""
    try:
        _ensure_data_dir()
        with open(POWER_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error writing power.json: {e}")
        return False


def _is_service_installed():
    """Check if StressTestWakeService is installed."""
    try:
        result = subprocess.run(
            ['sc', 'query', SERVICE_NAME],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except:
        return False


def _is_service_running():
    """Check if StressTestWakeService is running."""
    try:
        result = subprocess.run(
            ['sc', 'query', SERVICE_NAME],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return "RUNNING" in result.stdout
        return False
    except:
        return False


def _start_service():
    """Start StressTestWakeService."""
    try:
        logger.info(f"Starting {SERVICE_NAME}...")
        result = subprocess.run(
            ['sc', 'start', SERVICE_NAME],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 or "already been started" in result.stdout:
            logger.info(f"Service {SERVICE_NAME} started")
            
            # Wait for service to be ready
            for _ in range(10):
                if _is_service_running():
                    return True
                time.sleep(0.5)
            return True
        else:
            logger.error(f"Failed to start service: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error starting service: {e}")
        return False


def _install_and_start_service():
    """Install and start StressTestWakeService (lazy installation)."""
    try:
        installer_script = os.path.join(SERVICE_DIR, 'wake_service_install.py')
        
        if not os.path.exists(installer_script):
            logger.error(f"Service installer not found: {installer_script}")
            return False
        
        logger.info("Installing StressTestWakeService...")
        
        # Install service
        result = subprocess.run(
            [sys.executable, installer_script, 'install'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Service installation failed: {result.stderr}")
            return False
        
        logger.info("Service installed successfully")
        
        # Start service
        return _start_service()
        
    except Exception as e:
        logger.error(f"Error installing service: {e}")
        return False


def _ensure_service_running():
    """Ensure service is installed and running (lazy installation)."""
    # Check if service is already running
    if _is_service_running():
        return True
    
    # Check if service is installed but not running
    if _is_service_installed():
        return _start_service()
    
    # Service not installed - install and start
    return _install_and_start_service()


def _schedule_wake_with_service(duration_seconds, caller="unknown"):
    """Schedule wake timer via service by writing to power.json."""
    try:
        data = _read_power_json()
        if not data:
            # Initialize if not exists
            data = {
                "service_config": {
                    "service_name": SERVICE_NAME,
                    "log_level": "INFO",
                    "max_history_entries": 100
                },
                "current_state": {
                    "service_running": False,
                    "last_wake_time": None,
                    "pending_wake_schedule": None
                },
                "wake_schedule": None,
                "wake_history": []
            }
        
        # Create wake schedule request
        schedule = {
            "task_name": "WakeFromS0_Service",
            "duration_seconds": duration_seconds,
            "sleep_start": datetime.now().isoformat(),
            "created_by": caller
        }
        
        data['wake_schedule'] = schedule
        
        if _write_power_json(data):
            logger.info(f"Wake schedule written to power.json: {duration_seconds}s")
            return True
        else:
            logger.error("Failed to write wake schedule to power.json")
            return False
            
    except Exception as e:
        logger.error(f"Error scheduling wake: {e}")
        return False


def _wait_for_wake_completion(duration_seconds, timeout_buffer=60):
    """Wait for wake completion with timeout."""
    timeout = duration_seconds + timeout_buffer
    start_time = time.time()
    last_schedule = None
    
    logger.info(f"Waiting for wake completion (timeout: {timeout}s)...")
    
    while time.time() - start_time < timeout:
        data = _read_power_json()
        if data:
            current_schedule = data.get('wake_schedule')
            
            # Check if wake schedule has been cleared (indicates completion)
            if current_schedule is None and \
               data['current_state'].get('pending_wake_schedule') is None:
                
                # Only log completion if we previously had a schedule
                if last_schedule is not None:
                    logger.info("Wake completed successfully")
                    
                    # Get last wake history entry
                    if data.get('wake_history'):
                        last_wake = data['wake_history'][-1]
                        logger.info(f"Wake duration: {last_wake.get('duration_actual')}s "
                                  f"(expected: {last_wake.get('duration_expected')}s, "
                                  f"drift: {last_wake.get('drift')}s)")
                    
                    return True
            
            last_schedule = current_schedule
        
        time.sleep(1)
    
    logger.warning(f"Wake completion timeout after {timeout}s")
    return False


def _force_display_wake():
    """Force display wake (fallback if service wake fails)."""
    try:
        logger.info("Forcing display wake...")
        
        # Turn Monitor ON
        user32.PostMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON)
        
        # Force display on
        kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        
        logger.info("Display wake completed")
        return True
    except Exception as e:
        logger.error(f"Error forcing display wake: {e}")
        return False


def enter_s0_with_service(duration_seconds: int):
    """
    Enter S0 Modern Standby using Windows Service for reliable wake.
    
    This function uses StressTestWakeService to manage wake timers.
    The service survives S0 sleep and ensures automatic wake without
    requiring manual user input.
    
    Args:
        duration_seconds: Duration to sleep before automatic wake
        
    Returns:
        bool: True if wake successful, False otherwise
        
    Note:
        - Automatically installs service if not present (lazy installation)
        - Falls back to manual wake if service fails
        - Requires administrator privileges
        - Maintains S0 Modern Standby (does not force S3)
    """
    try:
        logger.info(f"Entering S0 Modern Standby with service-managed wake ({duration_seconds}s)...")
        
        # Ensure service is running (lazy install if needed)
        if not _ensure_service_running():
            logger.error("Failed to start service, falling back to manual wake")
            # Fallback to original function
            return enter_s0_and_wake(duration_seconds)
        
        # Schedule wake via service
        if not _schedule_wake_with_service(duration_seconds, caller="util_power"):
            logger.error("Failed to schedule wake, falling back to manual wake")
            return enter_s0_and_wake(duration_seconds)
        
        # Record sleep start time
        sleep_start = time.time()
        
        # Turn Monitor OFF to enter S0
        logger.info("Turning monitor OFF (entering S0)...")
        user32.PostMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
        
        logger.info(f"S0 sleep initiated at {datetime.now().strftime('%H:%M:%S')}")
        logger.info(f"Wake timer will trigger in {duration_seconds}s...")
        
        # Wait for wake completion with timeout
        wake_success = _wait_for_wake_completion(duration_seconds, timeout_buffer=60)
        
        actual_duration = time.time() - sleep_start
        
        if wake_success:
            logger.info(f"[OK] Wake completed successfully after {actual_duration:.2f}s")
        else:
            logger.warning(f"[WARN] Wake timeout - forcing manual display wake")
            _force_display_wake()
            logger.warning(f"Manual wake completed after {actual_duration:.2f}s")
        
        # Ensure display is on
        _force_display_wake()
        
        return wake_success
        
    except Exception as e:
        logger.error(f"Error in enter_s0_with_service: {e}")
        logger.info("Attempting fallback to manual wake...")
        _force_display_wake()
        return False

def enter_s0_and_wake(duration_seconds: int):
    """
    Enter S0 Modern Standby with manual wake (legacy method).
    
    This is the original implementation that requires manual user input
    to resume after the wake timer triggers.
    
    Args:
        duration_seconds: Duration to sleep before wake timer triggers
        
    Returns:
        bool: True if completed, False otherwise
        
    Note:
        - Wake timer triggers but requires manual keypress to resume
        - Use enter_s0_with_service() for automatic wake without user input
    """
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
    
    # Test the new service-based wake
    print("\nTesting S0 wake with service (10 seconds)...\n")
    success = enter_s0_with_service(10)
    
    if success:
        print("\n[OK] Service-based wake test completed successfully")
    else:
        print("\n[ERROR] Service-based wake test failed")
    
    # Optionally test legacy method
    # print("\nTesting legacy manual wake (10 seconds)...\n")
    # enter_s0_and_wake(10)
