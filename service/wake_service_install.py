"""
Service Installation and Management Utility

Handles installation, removal, and management of StressTestWakeService.
"""

import sys
import os
import subprocess
import time
import io

# Force UTF-8 encoding for stdout/stderr
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SERVICE_NAME = "StressTestWakeService"


def is_admin():
    """Check if running with administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin(args):
    """Re-run script with administrator privileges."""
    import ctypes
    script = os.path.abspath(__file__)
    params = ' '.join(args)
    
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
        return True
    except:
        return False


def install_service():
    """Install the Windows Service."""
    print("Installing StressTestWakeService...")
    
    service_script = os.path.join(os.path.dirname(__file__), 'wake_service.py')
    
    try:
        # Install service
        result = subprocess.run(
            [sys.executable, service_script, 'install'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[OK] Service installed successfully")
            
            # Set service to auto-start
            subprocess.run(['sc', 'config', SERVICE_NAME, 'start=', 'auto'], 
                          capture_output=True)
            
            return True
        else:
            print(f"[ERROR] Installation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error installing service: {e}")
        return False


def start_service():
    """Start the Windows Service."""
    print("Starting StressTestWakeService...")
    
    try:
        result = subprocess.run(
            ['sc', 'start', SERVICE_NAME],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 or "already been started" in result.stdout:
            print("[OK] Service started successfully")
            return True
        else:
            print(f"[ERROR] Failed to start service: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error starting service: {e}")
        return False


def stop_service():
    """Stop the Windows Service."""
    print("Stopping StressTestWakeService...")
    
    try:
        result = subprocess.run(
            ['sc', 'stop', SERVICE_NAME],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[OK] Service stopped successfully")
            return True
        else:
            print(f"[ERROR] Failed to stop service: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error stopping service: {e}")
        return False


def remove_service():
    """Remove the Windows Service."""
    print("Removing StressTestWakeService...")
    
    # Stop service first
    stop_service()
    time.sleep(2)
    
    service_script = os.path.join(os.path.dirname(__file__), 'wake_service.py')
    
    try:
        result = subprocess.run(
            [sys.executable, service_script, 'remove'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[OK] Service removed successfully")
            return True
        else:
            print(f"[ERROR] Removal failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error removing service: {e}")
        return False


def query_service():
    """Query service status."""
    try:
        result = subprocess.run(
            ['sc', 'query', SERVICE_NAME],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"\n{result.stdout}")
            
            if "RUNNING" in result.stdout:
                return "running"
            elif "STOPPED" in result.stdout:
                return "stopped"
            else:
                return "unknown"
        else:
            print(f"Service not found or error: {result.stderr}")
            return "not_installed"
            
    except Exception as e:
        print(f"Error querying service: {e}")
        return "error"


def show_help():
    """Show usage information."""
    print("""
StressTestWakeService Management Utility

Usage:
    python wake_service_install.py [command]

Commands:
    install     - Install the service
    remove      - Remove the service
    start       - Start the service
    stop        - Stop the service
    restart     - Restart the service
    status      - Query service status
    help        - Show this help message

Examples:
    python wake_service_install.py install
    python wake_service_install.py status

Note: Requires administrator privileges.
""")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # Check admin privileges
    if command not in ['help', 'status']:
        if not is_admin():
            print("Administrator privileges required. Attempting to elevate...")
            if run_as_admin(sys.argv[1:]):
                sys.exit(0)
            else:
                print("[ERROR] Failed to elevate privileges. Please run as administrator.")
                sys.exit(1)
    
    # Execute command
    if command == 'install':
        if install_service():
            start_service()
    elif command == 'remove':
        remove_service()
    elif command == 'start':
        start_service()
    elif command == 'stop':
        stop_service()
    elif command == 'restart':
        stop_service()
        time.sleep(2)
        start_service()
    elif command == 'status':
        query_service()
    elif command == 'help':
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
