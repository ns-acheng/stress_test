import subprocess
import datetime
import os
import logging
import sys

logger = logging.getLogger()

def create_wake_task(task_name: str, wake_time_seconds: int, script_path: str):
    """
    Creates a Windows Scheduled Task that wakes the computer to run a script.
    
    Args:
        task_name: Name of the task.
        wake_time_seconds: Seconds from now to trigger the task.
        script_path: Path to the script/executable to run.
    """
    # Calculate start time
    # schtasks requires time in HH:mm:ss format
    # We add a small buffer (e.g. 2 seconds) to ensure the system has time to register it
    run_time = datetime.datetime.now() + datetime.timedelta(seconds=wake_time_seconds)
    start_time_str = run_time.strftime("%H:%M:%S")
    start_date_str = run_time.strftime("%d/%m/%Y") # System locale dependent, but usually works

    # Command to run: python.exe <script_path>
    # We use the current python interpreter
    python_exe = sys.executable
    
    # Construct schtasks command
    # /SC ONCE : Run once
    # /ST : Start Time
    # /SD : Start Date
    # /TR : Task Run (command)
    # /RL HIGHEST : Run with highest privileges
    # /F : Force create (overwrite)
    
    # Note: We cannot easily set "Wake the computer" via command line schtasks.exe in one go for all versions.
    # However, we can create it via XML or use PowerShell. PowerShell is more robust.
    
    # PowerShell script to create the task with WakeToRun settings
    ps_script = f"""
    $Action = New-ScheduledTaskAction -Execute "{python_exe}" -Argument "{script_path}"
    $Trigger = New-ScheduledTaskTrigger -Once -At "{run_time.strftime('%Y-%m-%d %H:%M:%S')}"
    $Settings = New-ScheduledTaskSettingsSet -WakeToRun -Priority 1 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName "{task_name}" -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
    """
    
    try:
        # Run PowerShell command
        cmd = ["powershell", "-Command", ps_script]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Scheduled task '{task_name}' created to run at {start_time_str}.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create scheduled task: {e.stderr}")
        return False

def delete_wake_task(task_name: str):
    """Deletes the specified scheduled task."""
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            check=False # Don't raise if task doesn't exist
        )
        logger.info(f"Scheduled task '{task_name}' deleted.")
    except Exception as e:
        logger.warning(f"Error deleting task '{task_name}': {e}")

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    # create_wake_task("TestWake", 60, "c:\\mycode\\stress_test\\util_power.py")
