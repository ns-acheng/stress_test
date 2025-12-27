import ctypes
import time
import sys

# Define constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

def force_wake():
    print("Helper: Attempting to wake display...")
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    
    # 1. Set Thread Execution State
    # This tells the OS that the system and display are required.
    kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    )
    
    # 2. Simulate Mouse Input (Jiggle)
    # Simulating input is often required to break out of deep idle states where
    # programmatic requests might be ignored.
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
    for _ in range(10):
        send_mouse_input(1, 1)
        time.sleep(0.1)
        send_mouse_input(-1, -1)
        time.sleep(0.1)
        
    # 3. Keep alive for a bit to ensure the system processes the wake event
    time.sleep(10)

if __name__ == "__main__":
    try:
        force_wake()
    except Exception as e:
        print(f"Helper Error: {e}")
