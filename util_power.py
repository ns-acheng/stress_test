import ctypes
from ctypes import wintypes
import logging
import time

logger = logging.getLogger()

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

# Window Messages and Power Constants
HWND_BROADCAST = 0xFFFF
WM_SYSCOMMAND = 0x0112
SC_MONITORPOWER = 0xF170
MONITOR_OFF = 2
MONITOR_ON = -1

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
    # 1. Create the Timer
    hTimer = kernel32.CreateWaitableTimerW(None, False, None)
    if not hTimer:
        logger.error(f"Failed create timer. Err: {kernel32.GetLastError()}")
        return False

    # 2. Create Power Request Object
    # We prepare this beforehand so we can call it immediately upon waking
    reason = REASON_CONTEXT()
    reason.Version = POWER_REQUEST_CONTEXT_VERSION
    reason.Flags = POWER_REQUEST_CONTEXT_SIMPLE_STRING
    reason.Reason.SimpleReasonString = "Stress Test Wakeup"
    
    hPowerRequest = kernel32.PowerCreateRequest(ctypes.byref(reason))
    if not hPowerRequest:
        logger.error(f"Failed to create Power Request. Err: {kernel32.GetLastError()}")
        kernel32.CloseHandle(hTimer)
        return False

    try:
        # 3. Set the Timer
        now_sec = time.time()
        wake_time_sec = now_sec + duration_seconds
        file_time_val = int((wake_time_sec + 11644473600) * 10000000)
        li = LARGE_INTEGER(file_time_val & 0xFFFFFFFF, file_time_val >> 32)

        if not kernel32.SetWaitableTimer(hTimer, ctypes.byref(li), 0, None, None, True):
            logger.error(f"Failed set timer. Err: {kernel32.GetLastError()}")
            return False

        logger.info(f"Enter S0 (Monitor OFF) for {duration_seconds}s...")

        # 4. Turn Monitor OFF
        user32.PostMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
        
        # 5. Wait for Timer
        # The system will likely enter S0 Idle here.
        # When timer fires, SoC wakes up, but display stays off.
        wait_result = kernel32.WaitForSingleObject(
            hTimer, (duration_seconds + 5) * 1000)
        
        if wait_result == 0:
            logger.info("Timer expired. SoC is awake. Requesting Display ON...")
        else:
            logger.warning(f"Wait returned unexpected: {wait_result}")

        # 6. FORCE DISPLAY ON using PowerSetRequest
        # This tells the Power Manager: "I need the System AND Display running right now"
        if not kernel32.PowerSetRequest(hPowerRequest, PowerRequestSystemRequired):
             logger.error(
                 f"Failed to set SystemRequired. Err: {kernel32.GetLastError()}")
        
        if not kernel32.PowerSetRequest(hPowerRequest, PowerRequestDisplayRequired):
             logger.error(
                 f"Failed to set DisplayRequired. Err: {kernel32.GetLastError()}")

        # 7. Legacy Wake Methods (Backup)
        # Send the legacy monitor on message
        user32.PostMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON)
        
        # Simulate tiny mouse movement
        user32.mouse_event(0x0001, 1, 1, 0, 0) # MOUSEEVENTF_MOVE
        user32.mouse_event(0x0001, -1, -1, 0, 0)

        logger.info("Wake requests sent. Holding power request for 5 seconds to ensure screen lights up...")
        time.sleep(5) 

        # 8. Cleanup Power Request
        # Once we are sure the user is back or the test continues, we can clear the request
        kernel32.PowerClearRequest(hPowerRequest, PowerRequestSystemRequired)
        kernel32.PowerClearRequest(hPowerRequest, PowerRequestDisplayRequired)
        
        logger.info("Power request cleared.")
        return True

    finally:
        kernel32.CloseHandle(hTimer)
        kernel32.CloseHandle(hPowerRequest)

if __name__ == "__main__":
    from util_resources import enable_privilege
    from util_subprocess import enable_wake_timers

    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    enable_privilege("SeWakeAlarmPrivilege")
    enable_wake_timers()
    enter_s0_and_wake(10)
