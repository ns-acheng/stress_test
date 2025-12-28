"""
Demo: S0 Modern Standby with Service-Based Wake

This demonstrates the new service-based S0 wake functionality.
The system will:
1. Auto-install service if not present
2. Enter S0 Modern Standby (monitor off)
3. Wake automatically after specified duration
4. No manual keypress required
"""

import sys
import os
import logging
import io

# Force UTF-8 encoding for stdout/stderr
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from util_power import enter_s0_with_service
from util_resources import enable_privilege
from util_subprocess import enable_wake_timers

def main():
    """Demo the service-based S0 wake."""
    import subprocess
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger()
    
    print("=" * 60)
    print("S0 Modern Standby Service-Based Wake Demo")
    print("=" * 60)
    print()
    
    # Restart service with fresh code
    print("RESTARTING SERVICE WITH FRESH CODE...")
    print("-" * 60)
    
    print("Removing old service...")
    subprocess.run([sys.executable, 'service/wake_service_install.py', 'remove'], 
                   capture_output=True, text=True)
    
    print("Installing service with new code...")
    subprocess.run([sys.executable, 'service/wake_service_install.py', 'install'], 
                   capture_output=True, text=True)
    
    print("Starting service...")
    subprocess.run(['sc', 'start', 'StressTestWakeService'], 
                   capture_output=True, text=True)
    
    print("Waiting for service to initialize...")
    import time
    time.sleep(3)
    
    print("[OK] Service restart complete")
    print("-" * 60)
    print()
    
    print("This will:")
    print("  1. Install StressTestWakeService (if needed)")
    print("  2. Enter S0 Modern Standby for 10 seconds")
    print("  3. Automatically wake without user input")
    print("  4. Report wake timing and drift")
    print()
    print("Note: Requires administrator privileges")
    print("=" * 60)
    print()
    
    input("Press Enter to start demo...")
    print()
    
    # Enable required privileges
    logger.info("Enabling wake privileges...")
    enable_privilege("SeWakeAlarmPrivilege")
    enable_wake_timers()
    
    # Run S0 wake test
    logger.info("Starting S0 wake test...")
    print()
    
    success = enter_s0_with_service(10)
    
    print()
    print("=" * 60)
    if success:
        print("[OK] Demo completed successfully!")
        print("  - Service auto-installed and started")
        print("  - S0 sleep initiated")
        print("  - Automatic wake triggered")
        print("  - No manual input required")
    else:
        print("[ERROR] Demo encountered issues")
        print("  - Check log/wake_service.log for details")
        print("  - Service may need manual installation")
    print("=" * 60)
    print()
    
    # Show service status
    import subprocess
    try:
        result = subprocess.run(
            ['sc', 'query', 'StressTestWakeService'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("\nService Status:")
            print(result.stdout)
    except:
        pass
    
    # Check if wake task was created
    print("\nTask Scheduler Check:")
    try:
        task_result = subprocess.run(
            ['schtasks', '/query', '/tn', 'WakeFromS0_Service', '/fo', 'LIST'],
            capture_output=True,
            text=True
        )
        if task_result.returncode == 0:
            print("[OK] Wake task exists")
            for line in task_result.stdout.split('\n'):
                if 'Task Name' in line or 'Status' in line or 'Last Run Time' in line or 'Next Run Time' in line:
                    print(f"  {line.strip()}")
        else:
            print("[ERROR] Wake task NOT found - service failed to create it")
            print("This is why manual wake was needed!")
    except:
        pass
    
    # Check service log for errors
    print("\nService Log Check:")
    log_file = os.path.join(os.path.dirname(__file__), 'log', 'wake_service.log')
    if os.path.exists(log_file):
        print(f"Reading: {log_file}")
        print("-" * 60)
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Show last 20 lines or all if fewer
            recent_lines = lines[-20:] if len(lines) > 20 else lines
            for line in recent_lines:
                print(line.rstrip())
        except Exception as e:
            print(f"[ERROR] Could not read log: {e}")
    else:
        print(f"[WARN] Service log not found at: {log_file}")
        print("Service may not be logging properly")


if __name__ == '__main__':
    main()
