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
VK_SHIFT = 0x10
MOUSEEVENTF_MOVE = 0x0001
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD),
                ("HighPart", wintypes.LONG)]

def enter_s0_and_wake(duration_seconds: int):
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

        kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )

        user32.SendMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON
        )

        user32.mouse_event(MOUSEEVENTF_MOVE, 1, 1, 0, 0)
        user32.mouse_event(MOUSEEVENTF_MOVE, -1, -1, 0, 0)

        user32.keybd_event(VK_SHIFT, 0, 0, 0)
        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)

        kernel32.SetThreadExecutionState(ES_CONTINUOUS)

        logger.info("System Woke (Monitor ON).")
        return True

    finally:
        kernel32.CloseHandle(handle)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    enter_s0_and_wake(25)