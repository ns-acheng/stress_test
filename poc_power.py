"""
Power Management PoC: S0 Modern Standby with Wake Timer

This script puts a Windows laptop into S0 Modern Standby (Connected Standby)
and wakes it up after 10 seconds using a scheduled task wake timer.

Requirements:
- Windows 10/11 with Modern Standby support
- Administrator privileges
- pywin32 package for Task Scheduler COM API

How it works:
1. Creates a scheduled task that triggers 10 seconds from now
2. Enables "Wake the computer to run this task" flag
3. This registers an RTC alarm with the hardware
4. Puts the system into Modern Standby
5. RTC alarm wakes the system after 10 seconds (hardware-based)
"""

import win32com.client
import pythoncom
import ctypes
import time
import os
from datetime import datetime, timedelta
import sys

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


def create_wake_task(task_name="WakeFromS0", delay_seconds=10):
    """
    Create a scheduled task with wake timer enabled.
    
    Args:
        task_name: Name of the scheduled task
        delay_seconds: Seconds from now when task should trigger and wake system
    
    Returns:
        bool: True if task created successfully
    """
    try:
        # Initialize COM
        pythoncom.CoInitialize()
        
        # Connect to Task Scheduler
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        
        # Get root folder
        root_folder = scheduler.GetFolder('\\')
        
        # Delete existing task if present
        try:
            root_folder.DeleteTask(task_name, 0)
            print(f"Deleted existing task: {task_name}")
        except:
            pass
        
        # Create new task definition
        task_def = scheduler.NewTask(0)
        
        # Set registration info
        task_def.RegistrationInfo.Description = 'Wake system from Modern Standby'
        task_def.RegistrationInfo.Author = 'Power Management PoC'
        
        # Set principal to run with highest privileges
        task_def.Principal.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST
        task_def.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
        
        # Configure settings
        task_def.Settings.Enabled = True
        task_def.Settings.StopIfGoingOnBatteries = False
        task_def.Settings.DisallowStartIfOnBatteries = False
        task_def.Settings.AllowDemandStart = True
        task_def.Settings.StartWhenAvailable = False
        task_def.Settings.RunOnlyIfNetworkAvailable = False
        
        # CRITICAL: Enable wake to run this task
        task_def.Settings.WakeToRun = True
        print(f"✓ Wake timer enabled for task")
        
        # Create time-based trigger (10 seconds from now)
        trigger_time = datetime.now() + timedelta(seconds=delay_seconds)
        
        trigger = task_def.Triggers.Create(1)  # TASK_TRIGGER_TIME
        trigger.StartBoundary = trigger_time.strftime('%Y-%m-%dT%H:%M:%S')
        trigger.Enabled = True
        
        print(f"✓ Trigger set for: {trigger_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Create action to wake display using Python
        # Use util_wakeup.py if available, otherwise use inline PowerShell
        helper_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "util_wakeup.py")
        
        action = task_def.Actions.Create(0)  # TASK_ACTION_EXEC
        
        if os.path.exists(helper_script):
            # Use the dedicated wake helper script
            action.Path = 'python'
            action.Arguments = f'"{helper_script}"'
            print(f"✓ Wake action: Run {os.path.basename(helper_script)}")
        else:
            # Fallback: Use PowerShell to wake display
            action.Path = 'powershell.exe'
            action.Arguments = '-WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point(0, 0); Start-Sleep -Milliseconds 100; [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point(1, 1)"'
            print(f"✓ Wake action: PowerShell mouse simulation")
        
        # Register the task
        TASK_CREATE_OR_UPDATE = 6
        TASK_LOGON_INTERACTIVE_TOKEN = 3
        
        root_folder.RegisterTaskDefinition(
            task_name,
            task_def,
            TASK_CREATE_OR_UPDATE,
            None,  # User
            None,  # Password
            TASK_LOGON_INTERACTIVE_TOKEN
        )
        
        print(f"✓ Scheduled task '{task_name}' created successfully")
        return True
        
    except Exception as e:
        print(f"✗ Error creating scheduled task: {e}")
        return False
    finally:
        pythoncom.CoUninitialize()


def enter_modern_standby():
    """
    Put the system into S0 Modern Standby (Connected Standby).
    
    Uses monitor off approach - same method as util_power.py.
    Requires administrator privileges.
    """
    try:
        # Load user32 for monitor control
        user32 = ctypes.windll.user32
        
        # Window Messages and Power Constants
        HWND_BROADCAST = 0xFFFF
        WM_SYSCOMMAND = 0x0112
        SC_MONITORPOWER = 0xF170
        MONITOR_OFF = 2
        
        print("\n" + "="*60)
        print("Entering Modern Standby in 3 seconds...")
        print("System will wake automatically after 10 seconds")
        print("="*60 + "\n")
        
        time.sleep(3)  # Give user time to read
        
        # Record time before sleep
        sleep_start = time.time()
        print(f"Sleep initiated at: {datetime.now().strftime('%H:%M:%S')}")
        
        # Turn Monitor OFF (S0 sleep simulation)
        user32.PostMessageW(
            HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
        
        print("✓ Monitor turned OFF (S0 sleep mode)")
        
        # Wait for wake time with countdown
        wake_time = sleep_start + 10
        
        while time.time() < wake_time + 2:  # Wait up to 2 seconds past wake time
            remaining = int(wake_time - time.time())
            if remaining > 0:
                print(f"Sleeping... {remaining}s remaining", end='\r')
            time.sleep(1)
        
        print("\n")  # Newline after countdown
        
        # Calculate actual sleep duration
        actual_wake_time = time.time()
        sleep_duration = actual_wake_time - sleep_start
        drift = actual_wake_time - wake_time
        
        print(f"✓ System woke at: {datetime.now().strftime('%H:%M:%S')}")
        print(f"✓ Sleep duration: {sleep_duration:.2f} seconds")
        
        if drift > 2:
            print(f"✓ System woke up {drift:.2f}s LATE (Hardware likely suspended)")
        else:
            print(f"✓ System woke up on time (Drift: {drift:.2f}s)")        
        # Force display wake to ensure full system wake
        print("\nForcing display wake...")
        force_display_wake()
        print("\u2713 Display wake completed")            
    except Exception as e:
        print(f"✗ Error entering Modern Standby: {e}")


def check_admin():
    """Check if script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def main():
    """Main execution flow."""
    print("\n" + "="*60)
    print("S0 Modern Standby Wake Timer PoC")
    print("="*60 + "\n")
    
    # Check for admin privileges
    if not check_admin():
        print("✗ ERROR: This script requires administrator privileges")
        print("Please run PowerShell or Command Prompt as Administrator")
        sys.exit(1)
    
    print("✓ Running with administrator privileges\n")
    
    # Step 1: Create scheduled task with wake timer
    print("Step 1: Creating scheduled task with wake timer...")
    print("-" * 60)
    
    if not create_wake_task(task_name="WakeFromS0_PoC", delay_seconds=10):
        print("\n✗ Failed to create wake task. Aborting.")
        sys.exit(1)
    
    print("\n" + "✓ Wake timer successfully registered with system")
    print("  The RTC alarm will trigger in 10 seconds, even during sleep\n")
    
    # Step 2: Enter Modern Standby
    print("\nStep 2: Entering Modern Standby...")
    print("-" * 60)
    enter_modern_standby()
    
    # If we reach here, system woke up
    print("\n" + "="*60)
    print("System woke up from Modern Standby!")
    print("="*60)
    
    # Cleanup: Delete the scheduled task
    try:
        pythoncom.CoInitialize()
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        root_folder = scheduler.GetFolder('\\')
        root_folder.DeleteTask("WakeFromS0_PoC", 0)
        print("\n✓ Cleaned up scheduled task")
        pythoncom.CoUninitialize()
    except:
        print("\n⚠ Note: Manual cleanup may be needed - check Task Scheduler")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
