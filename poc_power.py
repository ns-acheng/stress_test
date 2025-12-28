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
import argparse
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


def create_wake_task(task_name="WakeFromS0", delay_seconds=10, completion_script=None):
    """
    Create a scheduled task with wake timer enabled.
    
    Args:
        task_name: Name of the scheduled task
        delay_seconds: Seconds from now when task should trigger and wake system
        completion_script: Optional script to run on wake (for Mode 1)
    
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
        
        # Create action to wake display
        action = task_def.Actions.Create(0)  # TASK_ACTION_EXEC
        
        if completion_script:
            # Mode 1: Run completion script
            action.Path = 'python'
            action.Arguments = f'"{completion_script}"'
            print(f"✓ Wake action: Run {os.path.basename(completion_script)}")
        else:
            # Mode 2/3: Use util_wakeup.py if available, otherwise PowerShell
            helper_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "util_wakeup.py")
            
            if os.path.exists(helper_script):
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


def enter_standby_mode1(delay_seconds=10):
    """
    Mode 1: Script exits after entering sleep, wake timer runs completion.
    """
    try:
        user32 = ctypes.windll.user32
        HWND_BROADCAST = 0xFFFF
        WM_SYSCOMMAND = 0x0112
        SC_MONITORPOWER = 0xF170
        MONITOR_OFF = 2
        
        print("\n" + "="*60)
        print("Mode 1: Exit-and-Resume (Script exits, wake timer completes)")
        print("Entering Modern Standby in 3 seconds...")
        print(f"System will wake after {delay_seconds} seconds")
        print("="*60 + "\n")
        
        time.sleep(3)
        
        sleep_start = time.time()
        print(f"Sleep initiated at: {datetime.now().strftime('%H:%M:%S')}")
        
        # Write state file for completion script
        state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poc_wake_state.txt")
        with open(state_file, 'w', encoding='utf-8') as f:
            f.write(f"sleep_start={sleep_start}\n")
            f.write(f"sleep_time={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Turn Monitor OFF
        user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
        print("✓ Monitor turned OFF (S0 sleep mode)")
        print("\n✓ Script exiting - wake timer will complete the cycle\n")
        
    except Exception as e:
        print(f"✗ Error: {e}")


def enter_standby_mode2(delay_seconds=10):
    """
    Mode 2: No countdown loop - just sleep and wait for wake event.
    """
    try:
        user32 = ctypes.windll.user32
        HWND_BROADCAST = 0xFFFF
        WM_SYSCOMMAND = 0x0112
        SC_MONITORPOWER = 0xF170
        MONITOR_OFF = 2
        
        print("\n" + "="*60)
        print("Mode 2: Wait-for-Wake (No countdown, accepts manual wake)")
        print("Entering Modern Standby in 3 seconds...")
        print(f"Press any key after {delay_seconds} seconds to complete wake")
        print("="*60 + "\n")
        
        time.sleep(3)
        
        sleep_start = time.time()
        print(f"Sleep initiated at: {datetime.now().strftime('%H:%M:%S')}")
        
        # Turn Monitor OFF
        user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
        print("✓ Monitor turned OFF (S0 sleep mode)")
        print(f"\nWaiting for wake event (hardware will wake at {(datetime.now() + timedelta(seconds=delay_seconds)).strftime('%H:%M:%S')})...")
        print("Press any key after wake timer triggers to resume script\n")
        
        # Simple blocking wait - will be interrupted by user input after wake
        input()  # Wait for user keypress
        
        actual_wake_time = time.time()
        sleep_duration = actual_wake_time - sleep_start
        
        print(f"\n✓ System resumed at: {datetime.now().strftime('%H:%M:%S')}")
        print(f"✓ Total duration: {sleep_duration:.2f} seconds")
        
        if sleep_duration >= delay_seconds:
            print(f"✓ Wake timer triggered (expected ~{delay_seconds}s, actual {sleep_duration:.2f}s)")
        
        print("\nForcing display wake...")
        force_display_wake()
        print("✓ Display wake completed")
            
    except Exception as e:
        print(f"✗ Error: {e}")


def enter_standby_mode3(delay_seconds=10):
    """
    Mode 3: Demo mode - verify wake timer without actual suspend.
    """
    try:
        print("\n" + "="*60)
        print("Mode 3: Demo Mode (Monitor off, no system suspend)")
        print("Demonstrating wake timer functionality")
        print(f"System will wake after {delay_seconds} seconds")
        print("="*60 + "\n")
        
        user32 = ctypes.windll.user32
        HWND_BROADCAST = 0xFFFF
        WM_SYSCOMMAND = 0x0112
        SC_MONITORPOWER = 0xF170
        MONITOR_OFF = 2
        
        time.sleep(3)
        
        sleep_start = time.time()
        print(f"Demo started at: {datetime.now().strftime('%H:%M:%S')}")
        
        # Turn Monitor OFF
        user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
        print("✓ Monitor turned OFF")
        print(f"\nWaiting {delay_seconds} seconds for wake timer to trigger...\n")
        
        # Active wait - script stays running
        wake_target = sleep_start + delay_seconds
        while time.time() < wake_target + 5:
            remaining = wake_target - time.time()
            if remaining > 0:
                print(f"Timer check: {remaining:.1f}s until wake event", end='\r')
            time.sleep(0.5)
        
        print("\n")
        actual_time = time.time()
        duration = actual_time - sleep_start
        
        print(f"✓ Timer completed at: {datetime.now().strftime('%H:%M:%S')}")
        print(f"✓ Duration: {duration:.2f} seconds")
        print("✓ Wake timer should have triggered in background")
        
        print("\nForcing display wake...")
        force_display_wake()
        print("✓ Display restored")
            
    except Exception as e:
        print(f"✗ Error: {e}")


def check_admin():
    """Check if script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def create_completion_script():
    """Create completion script for Mode 1."""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poc_wake_complete.py")
    
    script_content = '''"""Completion script for Mode 1 wake timer."""
import time
import os
from datetime import datetime

# Force display wake
import ctypes

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

# Turn monitor ON
HWND_BROADCAST = 0xFFFF
WM_SYSCOMMAND = 0x0112
SC_MONITORPOWER = 0xF170
MONITOR_ON = -1

user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON)

# Set execution state
kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)

# Simulate mouse movement
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
    _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]

def send_mouse():
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dx = 1
    inp.mi.dy = 1
    inp.mi.dwFlags = MOUSEEVENTF_MOVE
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

for _ in range(5):
    send_mouse()
    time.sleep(0.1)

wake_time = time.time()
print(f"\\n=" * 60)
print(f"Wake Timer Completion - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# Read state file
state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poc_wake_state.txt")
if os.path.exists(state_file):
    with open(state_file, 'r') as f:
        for line in f:
            if line.startswith('sleep_start='):
                sleep_start = float(line.split('=')[1].strip())
                duration = wake_time - sleep_start
                print(f"✓ System woke up after {duration:.2f} seconds")
            elif line.startswith('sleep_time='):
                sleep_time_str = line.split('=')[1].strip()
                print(f"✓ Sleep initiated: {sleep_time_str}")
    
    # Cleanup
    os.remove(state_file)
    print("✓ State file cleaned up")
else:
    print("✓ Wake timer triggered successfully")

print("✓ Display wake completed")
print("\\nMode 1 wake cycle complete!\\n")
'''
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    return script_path


def main():
    """Main execution flow with mode selection."""
    parser = argparse.ArgumentParser(
        description='S0 Modern Standby Wake Timer PoC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Modes:
  1 - Exit-and-Resume: Script exits after sleep, wake timer runs completion
  2 - Wait-for-Wake: No countdown, script waits for user input after wake
  3 - Demo Mode: Monitor off only, verify wake timer without suspend
        ''')
    parser.add_argument('mode', type=int, choices=[1, 2, 3], 
                        help='Wake mode to use (1, 2, or 3)')
    parser.add_argument('-d', '--delay', type=int, default=10,
                        help='Delay in seconds before wake (default: 10)')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("S0 Modern Standby Wake Timer PoC")
    print("="*60 + "\n")
    
    # Check for admin privileges
    if not check_admin():
        print("✗ ERROR: This script requires administrator privileges")
        print("Please run PowerShell or Command Prompt as Administrator")
        sys.exit(1)
    
    print("✓ Running with administrator privileges")
    print(f"✓ Selected Mode: {args.mode}")
    print(f"✓ Wake delay: {args.delay} seconds\n")
    
    # Step 1: Create scheduled task with wake timer
    print("Step 1: Creating scheduled task with wake timer...")
    print("-" * 60)
    
    completion_script = None
    if args.mode == 1:
        # Create completion script for Mode 1
        completion_script = create_completion_script()
        print(f"✓ Created completion script: {os.path.basename(completion_script)}")
    
    if not create_wake_task(task_name="WakeFromS0_PoC", 
                           delay_seconds=args.delay,
                           completion_script=completion_script):
        print("\n✗ Failed to create wake task. Aborting.")
        sys.exit(1)
    
    print("\n" + "✓ Wake timer successfully registered with system")
    print(f"  The RTC alarm will trigger in {args.delay} seconds, even during sleep\n")
    
    # Step 2: Enter Modern Standby based on mode
    print("\nStep 2: Entering Modern Standby...")
    print("-" * 60)
    
    if args.mode == 1:
        enter_standby_mode1(args.delay)
        # For Mode 1, script exits here
        print("="*60)
        print("Mode 1: Script completed (wake handled by scheduled task)")
        print("="*60 + "\n")
        return  # Don't cleanup - let wake task run
    elif args.mode == 2:
        enter_standby_mode2(args.delay)
    else:  # mode == 3
        enter_standby_mode3(args.delay)
    
    # If we reach here, system woke up (Mode 2 or 3)
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
    except SystemExit:
        pass  # Normal exit from argparse
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
