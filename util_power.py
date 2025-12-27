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
        # 3. Set the Timer (Relative Time)
        dt = int(duration_seconds * 10000000) * -1
        li = LARGE_INTEGER(dt & 0xFFFFFFFF, dt >> 32)

        if not kernel32.SetWaitableTimer(hTimer, ctypes.byref(li), 0, None, None, True):
            logger.error(f"Failed set timer. Err: {kernel32.GetLastError()}")
            return False

        logger.info(f"Enter S0 (Sleep) for {duration_seconds}s...")
        
        # Debug: Check if timer is registered
        try:
            import subprocess
            # Use 'cp950' (Traditional Chinese) or 'mbcs' (System Default) for decoding
            res = subprocess.run(
                ["powercfg", "/waketimers"], 
                capture_output=True, 
                encoding='cp950', 
                errors='replace'
            )
            logger.info(f"Active Wake Timers:\n{res.stdout.strip()}")
        except Exception as e:
            logger.warning(f"Failed to query waketimers: {e}")

        # 4. Explicitly request System Suspend (Sleep)
        # This works for both S3 and S0 Modern Standby
        # Args: Hibernate=False, Force=False, WakeupEventsDisabled=False
        logger.info("Calling SetSuspendState(Sleep)...")
        ctypes.windll.powrprof.SetSuspendState(False, False, False)
        
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
        
        # Simulate tiny mouse movement using SendInput (more reliable than mouse_event)
        INPUT_MOUSE = 0
        MOUSEEVENTF_MOVE = 0x0001
        
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", ctypes.c_long),
                        ("dy", ctypes.c_long),
                        ("mouseData", ctypes.c_ulong),
                        ("dwFlags", ctypes.c_ulong),
                        ("time", ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong),
                        ("mi", MOUSEINPUT)]

        def send_mouse_input(dx, dy):
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.mi.dx = dx
            inp.mi.dy = dy
            inp.mi.dwFlags = MOUSEEVENTF_MOVE
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        # Jiggle mouse a few times
        logger.info("Simulating mouse movement to wake display...")
        for i in range(5):
            send_mouse_input(1, 1)
            time.sleep(0.1)
            send_mouse_input(-1, -1)
            time.sleep(0.1)
            logger.info(f"Mouse jiggle {i+1}/5 performed.")

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
