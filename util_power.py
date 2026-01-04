import ctypes
from ctypes import wintypes
import logging

logger = logging.getLogger()
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

# Window Messages and Power Constants
HWND_BROADCAST = 0xFFFF
WM_SYSCOMMAND = 0x0112
SC_MONITORPOWER = 0xF170
MONITOR_OFF = 2
MONITOR_ON = -1

# Keyboard Event Flags
KEYEVENTF_KEYUP = 0x0002

class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD),
                ("HighPart", wintypes.LONG)]

def enter_s0_and_wake(duration_seconds: int) -> None:
    handle = kernel32.CreateWaitableTimerW(None, True, None)
    if not handle:
        logger.error(
            f"Failed create timer. Err: {kernel32.GetLastError()}"
        )
        return False

    try:
        dt = int(duration_seconds * 10000000) * -1
        li = LARGE_INTEGER(dt & 0xFFFFFFFF, dt >> 32)

        if not kernel32.SetWaitableTimer(
            handle, ctypes.byref(li), 0, None, None, True
        ):
            logger.error(
                f"Failed set timer. Err: {kernel32.GetLastError()}"
            )
            return False

        logger.info(f"Enter S0 (Monitor OFF) for {duration_seconds}s...")

        user32.SendMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF
        )

        kernel32.WaitForSingleObject(handle, -1)

        user32.SendMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON
        )

        # Simulate Key Press (0) and Key Release (KEYEVENTF_KEYUP)
        user32.keybd_event(0, 0, 0, 0)
        user32.keybd_event(0, 0, KEYEVENTF_KEYUP, 0)

        logger.info("System Woke (Monitor ON).")
        return True

    finally:
        kernel32.CloseHandle(handle)

if __name__ == "__main__":
    from util_log import LogSetup
    log_helper = LogSetup()
    log_helper.setup_logging()
    enter_s0_and_wake(45)
