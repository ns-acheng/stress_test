import subprocess
import os
import sys

def run_command(command, description):
    print(f"\n--- {description} ---")
    print(f"Command: {' '.join(command)}")
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except Exception as e:
        print(f"Error running command: {e}")

def check_scheduled_task_status(task_name):
    print(f"\n--- Checking Scheduled Task '{task_name}' ---")
    # Query the task to see its last run time and result
    run_command(["schtasks", "/Query", "/TN", task_name, "/V", "/FO", "LIST"], "Task Details")

def main():
    print("Collecting Power Management Diagnostics...")
    
    # 1. Check Power Capabilities (S0, S3, etc.)
    run_command(["powercfg", "/a"], "System Sleep States")
    
    # 2. Check Wake Timers (Are they allowed? Are any active?)
    run_command(["powercfg", "/waketimers"], "Active Wake Timers")
    
    # 3. Check Device Wake Armed (What devices can wake the system?)
    run_command(["powercfg", "/devicequery", "wake_armed"], "Devices Armed for Wake")
    
    # 4. Check Power Requests (What is preventing sleep?)
    run_command(["powercfg", "/requests"], "Active Power Requests")
    
    # 5. Check Current Power Scheme Settings (Specifically Wake Timers)
    # We need to find the GUID for "Allow wake timers" again to be sure
    run_command(["powercfg", "/q", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE"], "Wake Timer Setting (RTCWAKE)")
    
    # 6. Test Wake Timer Acceptance
    print("\n--- Testing Wake Timer Acceptance ---")
    print("Creating a test task 'DbgWakeTest' for 2 minutes from now...")
    # We need to calculate time 2 mins from now
    import datetime
    now = datetime.datetime.now()
    future = now + datetime.timedelta(minutes=2)
    start_time = future.strftime("%H:%M")
    
    # Create a dummy task
    # Note: This requires admin privileges usually, but we'll try.
    # We use a simple command like 'cmd /c echo hello'
    create_cmd = [
        "schtasks", "/Create", "/SC", "ONCE", "/TN", "DbgWakeTest", 
        "/TR", "cmd.exe /c echo hello", "/ST", start_time, "/F", "/RL", "HIGHEST"
    ]
    # Add /Z to mark it as wakeable? No, schtasks /Create doesn't have a simple /Wake flag in all versions?
    # Actually, standard schtasks /Create doesn't easily support "Wake the computer to run this task" via command line flags in all versions without XML.
    # But we can try to use PowerShell to create it properly like we did in util_task_scheduler.
    
    print("Using PowerShell to create a WakeToRun task...")
    ps_script = f"""
    $Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c echo hello"
    $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2)
    $Settings = New-ScheduledTaskSettingsSet -WakeToRun
    Register-ScheduledTask -TaskName "DbgWakeTest" -Action $Action -Trigger $Trigger -Settings $Settings -User "SYSTEM" -Force
    """
    
    # Write PS script to file to avoid escaping hell
    with open("dbg_create_task.ps1", "w", encoding='utf-8') as f:
        f.write(ps_script)
        
    run_command(["powershell", "-ExecutionPolicy", "Bypass", "-File", "dbg_create_task.ps1"], "Create Test Task")
    
    # Now check if it shows up in waketimers
    run_command(["powercfg", "/waketimers"], "Active Wake Timers (Should show DbgWakeTest)")
    
    # Cleanup
    run_command(["schtasks", "/Delete", "/TN", "DbgWakeTest", "/F"], "Cleanup Test Task")
    if os.path.exists("dbg_create_task.ps1"):
        os.remove("dbg_create_task.ps1")

    print("\n--- Diagnostics Complete ---")
    print("Please review the output above.")

if __name__ == "__main__":
    # If the user wants to check a specific task, they can pass it as an arg, 
    # but for now we just check general system state.
    main()
