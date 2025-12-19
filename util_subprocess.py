import subprocess
import os
import logging

logger = logging.getLogger()

def run_batch(batch_file: str):
    try:
        subprocess.Popen(["cmd", "/c", batch_file])
    except Exception as e:
        logger.error(f"Failed to run batch file {batch_file}: {e}")

def run_powershell(script_path, args=None):
    command = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", script_path
    ]
    
    if args:
        command.extend(args)
    
    try:
        logger.info(
            f"Running PowerShell: {script_path} {args if args else ''}"
        )
        subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True
        )
        logger.info("PowerShell script executed successfully.")

    except subprocess.CalledProcessError as e:
        logger.error(f"PowerShell failed. Return Code: {e.returncode}")
        err_msg = e.stderr.strip() if e.stderr else (
            e.stdout.strip() if e.stdout else "No output"
        )
        logger.error(f"Error details: {err_msg}")
    
    except FileNotFoundError:
        logger.error("PowerShell.exe not found in PATH.")

def run_curl(url: str):
    try:
        subprocess.Popen(
            ["curl", "-v", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        logger.error(f"Failed to run curl for {url}: {e}")

def _get_nsdiag_path(is_64bit: bool) -> str:
    if is_64bit:
        return r"C:\Program Files\Netskope\STAgent\nsdiag.exe"
    else:
        return r"C:\Program Files (x86)\Netskope\STAgent\nsdiag.exe"

def _run_nsdiag_generic(nsdiag_path: str, args: list, desc: str) -> bool:
    if not os.path.exists(nsdiag_path):
        logger.error(f"nsdiag.exe not found at: {nsdiag_path}")
        return False

    command = [nsdiag_path] + args
    try:        
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"nsdiag {desc} executed successfully.")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"nsdiag {desc} failed. RC: {e.returncode}")
        err = e.stderr.strip() if e.stderr else "Unknown error"
        logger.error(f"Details: {err}")
        return False

def nsdiag_collect_log(timestamp: str, is_64bit: bool, output_dir: str):
    nsdiag_path = _get_nsdiag_path(is_64bit)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_file = os.path.join(output_dir, f"{timestamp}_log_bundle.zip")
    success = _run_nsdiag_generic(
        nsdiag_path, ["-o", output_file], "log collection"
    )
    if success:
        logger.info(f"Log bundle created: {output_file}")

def nsdiag_update_config(is_64bit: bool = True):
    nsdiag_path = _get_nsdiag_path(is_64bit)
    _run_nsdiag_generic(nsdiag_path, ["-u"], "config update")

def nsdiag_enable_client(enable: bool, is_64bit: bool = True):
    nsdiag_path = _get_nsdiag_path(is_64bit)
    action = "enable" if enable else "disable"
    _run_nsdiag_generic(nsdiag_path, ["-t", action], f"client {action}")

def enable_wake_timers():
    subgroup = "238C9FA8-0AAD-41ED-83F4-97BE242C8F20" 
    setting  = "BD3B718A-0680-4D9D-8AB2-E1D2B4EF806D"
    val = "1"

    commands = [
        [
            "powercfg", "/setacvalueindex", "SCHEME_CURRENT", 
            subgroup, setting, val
        ],
        [
            "powercfg", "/setdcvalueindex", "SCHEME_CURRENT", 
            subgroup, setting, val
        ],
        ["powercfg", "/setactive", "SCHEME_CURRENT"]
    ]

    try:
        logger.info("Enabling 'Allow wake timers' in Power Settings...")
        for cmd in commands:
            subprocess.run(
                cmd, 
                check=True, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
        logger.info("Wake timers successfully enabled.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to enable wake timers: {e}")
        return False