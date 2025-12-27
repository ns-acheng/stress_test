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
import subprocess
from datetime import datetime, timedelta
import sys


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
        
        # Create action (simple command that does nothing)
        action = task_def.Actions.Create(0)  # TASK_ACTION_EXEC
        action.Path = 'cmd.exe'
        action.Arguments = '/c echo Wake timer triggered'
        
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
    
    Uses rundll32 to call SetSuspendState, which is more reliable than direct API.
    Requires administrator privileges.
    """
    try:
        print("\n" + "="*60)
        print("Entering Modern Standby in 3 seconds...")
        print("System will wake automatically after 10 seconds")
        print("="*60 + "\n")
        
        time.sleep(3)  # Give user time to read
        
        # Record time before sleep
        sleep_start = time.time()
        print(f"Sleep initiated at: {datetime.now().strftime('%H:%M:%S')}")
        
        # Use rundll32 to call SetSuspendState - more reliable than direct API
        # Parameters: Hibernate (0=sleep), ForceCritical (1=force), DisableWakeEvent (0=allow wake)
        result = subprocess.run(
            ['rundll32.exe', 'powrprof.dll,SetSuspendState', '0', '1', '0'],
            capture_output=True,
            timeout=2
        )
        
        # If we reach here, system has woken up
        wake_time = time.time()
        sleep_duration = wake_time - sleep_start
        
        print(f"\n✓ System woke at: {datetime.now().strftime('%H:%M:%S')}")
        print(f"✓ Sleep duration: {sleep_duration:.2f} seconds")
        
        # Verify system actually suspended (should be ~10 seconds, not immediate)
        if sleep_duration < 5:
            print(f"\n⚠ WARNING: Sleep duration too short ({sleep_duration:.2f}s)")
            print("  System may not have actually entered suspend state.")
            print("  This can happen if:")
            print("  - Modern Standby is not supported on this device")
            print("  - Power settings prevent sleep (USB wake, network wake, etc.)")
            print("  - Applications are holding wake locks")
            print("  - System is set to 'Never sleep' in power settings")
        else:
            print(f"✓ Verified: System was actually suspended for {sleep_duration:.2f}s")
            
    except subprocess.TimeoutExpired:
        # This is expected - the sleep command doesn't return until wake
        wake_time = time.time()
        sleep_duration = wake_time - sleep_start
        print(f"\n✓ System woke at: {datetime.now().strftime('%H:%M:%S')}")
        print(f"✓ Sleep duration: {sleep_duration:.2f} seconds")
        if sleep_duration >= 5:
            print(f"✓ Verified: System was actually suspended for {sleep_duration:.2f}s")
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
