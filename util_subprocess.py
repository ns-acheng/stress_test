import subprocess
import sys
import os

def run_batch(batch_file: str):
    try:
        subprocess.Popen(["cmd", "/c", batch_file])

    except subprocess.CalledProcessError as e:
        print(f"\n--- ERROR ---", file=sys.stderr)
        print(f"Command failed: {' '.join(e.cmd)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        
        error_message = e.stderr.strip() if e.stderr else "No error output."
        if not error_message and e.stdout:
             error_message = e.stdout.strip()

        print(f"Error details: {error_message}", file=sys.stderr)
        print("Exiting due to error.", file=sys.stderr)
    
    except FileNotFoundError as e:
        print(f"\n--- ERROR ---", file=sys.stderr)
        print(f"Command not found: {e.filename}", file=sys.stderr)
        print("Ensure the Windows System32 directory is in your PATH.", file=sys.stderr)


def run_powershell(script_path):
    command = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", script_path
    ]
    
    try:
        print(f"Attempting to run PowerShell script: {script_path}...")
        subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True
        )
        print(f"Successfully executed the PowerShell script.")

    except subprocess.CalledProcessError as e:
        print(f"\n--- ERROR ---", file=sys.stderr)
        print(f"Script failed: {' '.join(e.cmd)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        
        error_message = e.stderr.strip() if e.stderr else "No error output."
        if not error_message and e.stdout:
             error_message = e.stdout.strip()

        print(f"Error details: {error_message}", file=sys.stderr)
    
    except FileNotFoundError:
        print(f"\n--- ERROR ---", file=sys.stderr)
        print("PowerShell.exe not found.", file=sys.stderr)
        print("Ensure PowerShell is installed and in your system's PATH.", file=sys.stderr)

def _get_nsdiag_path(is_64bit: bool) -> str:
    if is_64bit:
        return r"C:\Program Files\Netskope\STAgent\nsdiag.exe"
    else:
        return r"C:\Program Files (x86)\Netskope\STAgent\nsdiag.exe"

def _run_nsdiag_generic(nsdiag_path: str, args: list, description: str) -> bool:
    if not os.path.exists(nsdiag_path):
        print(f"\n--- ERROR ---", file=sys.stderr)
        print(f"nsdiag.exe not found at: {nsdiag_path}", file=sys.stderr)
        return False

    command = [nsdiag_path] + args
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"nsdiag {description} executed successfully.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n--- ERROR ---", file=sys.stderr)
        print(f"nsdiag {description} failed: {' '.join(e.cmd)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        if e.stderr:
            print(f"Error details: {e.stderr.strip()}", file=sys.stderr)
        return False

def nsdiag_collect_log(timestamp: str, is_64bit: bool = True, log_path: str = None):
    nsdiag_path = _get_nsdiag_path(is_64bit)
    output_file = os.path.join(log_path, f"{timestamp}_log_bundle.zip")
    print(f"Start collecting logs using nsdiag...")
    if _run_nsdiag_generic(nsdiag_path, ["-o", output_file], "log collection"):
        print(f"Log bundle location: {output_file}")

def nsdiag_update_config(is_64bit: bool = True):
    nsdiag_path = _get_nsdiag_path(is_64bit)
    print(f"Start updating configuration using nsdiag...")
    if _run_nsdiag_generic(nsdiag_path, ["-u"], "config update"):
        print(f"Configuration update attempt completed.")