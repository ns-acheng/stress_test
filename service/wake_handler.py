"""
Wake Handler Script

Executed by Task Scheduler when wake timer triggers.
Forces display wake and logs completion to power.json.
"""

import ctypes
import time
import json
import os
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
POWER_JSON = os.path.join(DATA_DIR, 'power.json')
WAKE_COMPLETE = os.path.join(DATA_DIR, 'wake_complete.json')

# Constants for wake functionality
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
    """Simulate mouse movement to wake display."""
    user32 = ctypes.windll.user32
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dx = dx
    inp.mi.dy = dy
    inp.mi.dwFlags = MOUSEEVENTF_MOVE
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def force_display_wake():
    """Force display to wake using execution state and mouse simulation."""
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    
    # Set thread execution state to require display
    kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    )
    
    # Turn monitor ON
    HWND_BROADCAST = 0xFFFF
    WM_SYSCOMMAND = 0x0112
    SC_MONITORPOWER = 0xF170
    MONITOR_ON = -1
    
    user32.PostMessageW(
        HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON)
    
    # Simulate mouse movement to ensure wake
    for _ in range(5):
        send_mouse_input(1, 1)
        time.sleep(0.1)
        send_mouse_input(-1, -1)
        time.sleep(0.1)


def log_wake_completion():
    """Log wake completion data."""
    try:
        wake_time = time.time()
        
        # Read power.json to get sleep start time
        if os.path.exists(POWER_JSON):
            with open(POWER_JSON, 'r', encoding='utf-8') as f:
                power_data = json.load(f)
            
            schedule = power_data.get('wake_schedule')
            if schedule:
                sleep_start_str = schedule.get('sleep_start')
                expected_duration = schedule.get('duration_seconds', 0)
                
                # Calculate actual duration
                if sleep_start_str:
                    sleep_start = datetime.fromisoformat(sleep_start_str).timestamp()
                    actual_duration = wake_time - sleep_start
                    drift = actual_duration - expected_duration
                else:
                    sleep_start = None
                    actual_duration = 0
                    drift = 0
                
                # Create completion record
                completion_data = {
                    "sleep_start": sleep_start_str,
                    "wake_time": datetime.fromtimestamp(wake_time).isoformat(),
                    "duration_expected": expected_duration,
                    "duration_actual": round(actual_duration, 2),
                    "drift": round(drift, 2),
                    "success": True,
                    "created_by": schedule.get('created_by', 'unknown')
                }
                
                # Write completion data
                with open(WAKE_COMPLETE, 'w', encoding='utf-8') as f:
                    json.dump(completion_data, f, indent=2)
                
                return True
        
        return False
        
    except Exception as e:
        # Write error to completion file
        error_data = {
            "wake_time": datetime.now().isoformat(),
            "success": False,
            "error": str(e)
        }
        with open(WAKE_COMPLETE, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2)
        return False


if __name__ == '__main__':
    try:
        # Force display wake
        force_display_wake()
        
        # Log completion
        log_wake_completion()
        
    except Exception as e:
        # Ensure we write something even on error
        error_data = {
            "wake_time": datetime.now().isoformat(),
            "success": False,
            "error": str(e)
        }
        with open(WAKE_COMPLETE, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2)
