import ctypes
import time
import datetime
import os

# Define constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
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
    user32 = ctypes.windll.user32
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dx = dx
    inp.mi.dy = dy
    inp.mi.dwFlags = MOUSEEVENTF_MOVE
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

def log_wake(message):
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wakeup_log.txt")
    with open(log_file, "a") as f:
        f.write(f"{datetime.datetime.now()} - {message}\n")

def force_wake():
    log_wake("Helper: Attempting to wake display...")
    print("Helper: Attempting to wake display...")
    kernel32 = ctypes.windll.kernel32

    kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    )
    log_wake("Helper: SetThreadExecutionState called.")

    log_wake("Helper: Sending mouse input...")
    for _ in range(10):
        send_mouse_input(1, 1)
        time.sleep(0.1)
        send_mouse_input(-1, -1)
        time.sleep(0.1)
    log_wake("Helper: Mouse input sent. Exiting.")

if __name__ == "__main__":
    force_wake()
    send_mouse_input(-1, -1)
    time.sleep(10)

