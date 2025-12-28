"""
Service Wake Status Monitor

Real-time monitoring utility for StressTestWakeService and wake operations.
Displays current status, pending schedules, and recent wake history.
"""

import sys
import os
import time
import json
import subprocess
import io
from datetime import datetime

# Force UTF-8 encoding for stdout/stderr
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from util_power import (
    _is_service_installed,
    _is_service_running,
    _read_power_json,
    POWER_JSON,
    SERVICE_NAME
)


def clear_screen():
    """Clear console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_service_status():
    """Get detailed service status."""
    try:
        result = subprocess.run(
            ['sc', 'query', SERVICE_NAME],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            if "RUNNING" in result.stdout:
                return "RUNNING", "[OK]"
            elif "STOPPED" in result.stdout:
                return "STOPPED", "[STOP]"
            else:
                return "UNKNOWN", "[?]"
        else:
            return "NOT_INSTALLED", "[NO]"
    except:
        return "ERROR", "[ERR]"


def format_datetime(iso_str):
    """Format ISO datetime string to readable format."""
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return iso_str


def display_status(data, service_status, status_icon):
    """Display status dashboard."""
    clear_screen()
    
    print("=" * 70)
    print(" " * 20 + "S0 WAKE SERVICE MONITOR")
    print("=" * 70)
    print()
    
    # Service Status
    print(f"{status_icon} SERVICE STATUS: {service_status}")
    print()
    
    if not data:
        print("[WARN] power.json not found or unreadable")
        print()
        print("Press Ctrl+C to exit")
        return
    
    # Current State
    state = data.get('current_state', {})
    print("CURRENT STATE:")
    print(f"  Service Running:       {state.get('service_running', False)}")
    print(f"  Last Wake Time:        {format_datetime(state.get('last_wake_time'))}")
    print(f"  Last Error:            {state.get('last_error', 'None')}")
    print()
    
    # Pending Schedule
    schedule = data.get('wake_schedule')
    pending = state.get('pending_wake_schedule')
    
    if schedule or pending:
        print("PENDING WAKE SCHEDULE:")
        active_schedule = pending or schedule
        if active_schedule:
            print(f"  Task Name:             {active_schedule.get('task_name')}")
            print(f"  Duration:              {active_schedule.get('duration_seconds')}s")
            print(f"  Sleep Start:           {format_datetime(active_schedule.get('sleep_start'))}")
            print(f"  Requested By:          {active_schedule.get('created_by', 'unknown')}")
        print()
    else:
        print("PENDING WAKE SCHEDULE: None")
        print()
    
    # Wake History
    history = data.get('wake_history', [])
    print(f"WAKE HISTORY: ({len(history)} entries)")
    
    if history:
        print()
        print("  Recent Wakes:")
        print("  " + "-" * 66)
        print(f"  {'Wake Time':<20} {'Duration':<12} {'Drift':<10} {'Status':<10}")
        print("  " + "-" * 66)
        
        # Show last 5 entries
        for entry in history[-5:]:
            wake_time = format_datetime(entry.get('wake_time'))
            duration = f"{entry.get('duration_actual', 0):.2f}s"
            drift = f"{entry.get('drift', 0):.2f}s"
            status = "[OK]" if entry.get('success') else "[FAIL]"
            
            print(f"  {wake_time:<20} {duration:<12} {drift:<10} {status:<10}")
    else:
        print("  No wake history recorded yet")
    
    print()
    print("=" * 70)
    print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Press Ctrl+C to exit | Updates every 2 seconds")
    print()


def monitor_continuous():
    """Continuously monitor and display status."""
    print("Starting service monitor...")
    time.sleep(1)
    
    try:
        while True:
            data = _read_power_json()
            service_status, status_icon = get_service_status()
            
            display_status(data, service_status, status_icon)
            
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
        return


def show_history_details():
    """Show detailed wake history."""
    clear_screen()
    print("=" * 70)
    print(" " * 22 + "WAKE HISTORY DETAILS")
    print("=" * 70)
    print()
    
    data = _read_power_json()
    if not data:
        print("[WARN] power.json not found")
        return
    
    history = data.get('wake_history', [])
    
    if not history:
        print("No wake history recorded")
        return
    
    print(f"Total wake events: {len(history)}")
    print()
    
    for i, entry in enumerate(history, 1):
        print(f"Wake #{i}:")
        print(f"  Sleep Start:      {format_datetime(entry.get('sleep_start'))}")
        print(f"  Wake Time:        {format_datetime(entry.get('wake_time'))}")
        print(f"  Expected Duration: {entry.get('duration_expected')}s")
        print(f"  Actual Duration:   {entry.get('duration_actual')}s")
        print(f"  Drift:            {entry.get('drift')}s")
        print(f"  Success:          {'Yes' if entry.get('success') else 'No'}")
        print(f"  Requested By:     {entry.get('created_by', 'unknown')}")
        print()


def show_logs():
    """Show service log file."""
    clear_screen()
    print("=" * 70)
    print(" " * 25 + "SERVICE LOGS")
    print("=" * 70)
    print()
    
    log_file = os.path.join(os.path.dirname(POWER_JSON), '..', 'log', 'wake_service.log')
    
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        print(f"Showing last 50 log entries from {log_file}:")
        print()
        
        for line in lines[-50:]:
            print(line.rstrip())
            
    except Exception as e:
        print(f"Error reading log: {e}")


def show_menu():
    """Show interactive menu."""
    clear_screen()
    print("=" * 70)
    print(" " * 18 + "S0 WAKE SERVICE MONITOR - MENU")
    print("=" * 70)
    print()
    print("1. Live Status Monitor (updates every 2s)")
    print("2. View Wake History Details")
    print("3. View Service Logs")
    print("4. Service Control")
    print("5. Export power.json")
    print("6. Exit")
    print()
    
    choice = input("Select option (1-6): ").strip()
    return choice


def service_control_menu():
    """Service control submenu."""
    clear_screen()
    print("=" * 70)
    print(" " * 23 + "SERVICE CONTROL")
    print("=" * 70)
    print()
    
    service_status, status_icon = get_service_status()
    print(f"Current Status: {status_icon} {service_status}")
    print()
    print("1. Start Service")
    print("2. Stop Service")
    print("3. Restart Service")
    print("4. Query Status")
    print("5. Back to Main Menu")
    print()
    
    choice = input("Select option (1-5): ").strip()
    
    if choice == '1':
        print("\nStarting service...")
        subprocess.run(['sc', 'start', SERVICE_NAME])
        time.sleep(2)
    elif choice == '2':
        print("\nStopping service...")
        subprocess.run(['sc', 'stop', SERVICE_NAME])
        time.sleep(2)
    elif choice == '3':
        print("\nRestarting service...")
        subprocess.run(['sc', 'stop', SERVICE_NAME])
        time.sleep(2)
        subprocess.run(['sc', 'start', SERVICE_NAME])
        time.sleep(2)
    elif choice == '4':
        print("\nQuerying service status...")
        result = subprocess.run(['sc', 'query', SERVICE_NAME], capture_output=True, text=True)
        print(result.stdout)
        input("\nPress Enter to continue...")
    
    return choice != '5'


def export_power_json():
    """Export power.json to desktop."""
    try:
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        export_path = os.path.join(desktop, f'power_export_{int(time.time())}.json')
        
        data = _read_power_json()
        if data:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"\n[OK] Exported to: {export_path}")
        else:
            print("\n[ERROR] Failed to read power.json")
    except Exception as e:
        print(f"\n[ERROR] Export failed: {e}")
    
    input("\nPress Enter to continue...")


def main():
    """Main menu loop."""
    while True:
        choice = show_menu()
        
        if choice == '1':
            monitor_continuous()
        elif choice == '2':
            show_history_details()
            input("\nPress Enter to continue...")
        elif choice == '3':
            show_logs()
            input("\nPress Enter to continue...")
        elif choice == '4':
            while service_control_menu():
                pass
        elif choice == '5':
            export_power_json()
        elif choice == '6':
            print("\nExiting monitor...")
            break
        else:
            print("\nInvalid choice")
            time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
