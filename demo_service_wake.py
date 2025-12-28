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

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from util_power import enter_s0_with_service
from util_resources import enable_privilege
from util_subprocess import enable_wake_timers

def main():
    """Demo the service-based S0 wake."""
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
        print("✓ Demo completed successfully!")
        print("  - Service auto-installed and started")
        print("  - S0 sleep initiated")
        print("  - Automatic wake triggered")
        print("  - No manual input required")
    else:
        print("✗ Demo encountered issues")
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


if __name__ == '__main__':
    main()
