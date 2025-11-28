import subprocess
import sys
import os
import logging

# Get the existing logger so output goes to the same file as stress_test.py
logger = logging.getLogger()

def run_batch(batch_file: str):
    try:
        subprocess.Popen(["cmd", "/c", batch_file])
    except Exception as e:
        logger.error(f"Failed to run batch file {batch_file}: {e}")

def run_powershell(script_path):
    command = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", script_path
    ]
    
    try:
        logger.info(f"Running PowerShell: {script_path}")
        subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True
        )
        logger.info(f"PowerShell script executed successfully.")

    except subprocess.CalledProcessError as e:
        logger.error(f"PowerShell failed. Return Code: {e.returncode}")
        err_msg = e.stderr.strip() if e.stderr else (e.stdout.strip() if e.stdout else "No output")
        logger.error(f"Error details: {err_msg}")
    
    except FileNotFoundError:
        logger.error("PowerShell.exe not found in PATH.")

def _get_nsdiag_path(is_64bit: bool) -> str:
    if is_64bit:
        return r"C:\Program Files\Netskope\STAgent\nsdiag.exe"
    else:
        return r"C:\Program Files (x86)\Netskope\STAgent\nsdiag.exe"

def _run_nsdiag_generic(nsdiag_path: str, args: list, description: str) -> bool:
    if not os.path.exists(nsdiag_path):
        logger.error(f"nsdiag.exe not found at: {nsdiag_path}")
        return False

    command = [nsdiag_path] + args
    try:
        # logger.info(f"Running nsdiag {description}...")
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"nsdiag {description} executed successfully.")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"nsdiag {description} failed. RC: {e.returncode}")
        err = e.stderr.strip() if e.stderr else "Unknown error"
        logger.error(f"Details: {err}")
        return False

def nsdiag_collect_log(timestamp: str, is_64bit: bool = True):
    nsdiag_path = _get_nsdiag_path(is_64bit)
    cwd = os.getcwd()
    log_folder = os.path.join(cwd, "log")
    
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)

    output_file = os.path.join(log_folder, f"{timestamp}_log_bundle.zip")
    success = _run_nsdiag_generic(nsdiag_path, ["-o", output_file], "log collection")
    if success:
        logger.info(f"Log bundle created: {output_file}")

def nsdiag_update_config(is_64bit: bool = True):
    nsdiag_path = _get_nsdiag_path(is_64bit)
    _run_nsdiag_generic(nsdiag_path, ["-u"], "config update")