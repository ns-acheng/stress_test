import ctypes
from ctypes import wintypes
import logging

logger = logging.getLogger()

kernel32 = ctypes.windll.kernel32
powrprof = ctypes.windll.powrprof

class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD),
                ("HighPart", wintypes.LONG)]

def enter_s0_and_wake(duration_seconds: int):
    handle = kernel32.CreateWaitableTimerW(None, True, None)
    if not handle:
        logger.error(f"Failed to create Waitable Timer. Error: {kernel32.GetLastError()}")
        return False

    try:
        dt = int(duration_seconds * 10000000) * -1
        li = LARGE_INTEGER(dt & 0xFFFFFFFF, dt >> 32)

        if not kernel32.SetWaitableTimer(handle, ctypes.byref(li), 0, None, None, True):
            logger.error(f"Failed to set Wake Timer. Error: {kernel32.GetLastError()}")
            return False

        logger.info(f"System entering Standby for {duration_seconds}s (Wake Timer set)...")
        
        success = powrprof.SetSuspendState(False, False, False)
        
        if not success:
            logger.error(f"SetSuspendState failed. Error: {kernel32.GetLastError()}")
            return False

        kernel32.WaitForSingleObject(handle, -1)

        logger.info("System has WOKEN up from Standby.")
        return True

    finally:
        kernel32.CloseHandle(handle)


if __name__ == "__main__":
    enter_s0_and_wake(60)