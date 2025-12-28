# Quick Diagnostic Script
import subprocess
import os
import json
import sys

print("=" * 60)
print("WAKE SYSTEM DIAGNOSTICS")
print("=" * 60)
print()

print("RESTARTING SERVICE WITH FRESH CODE...")
print("=" * 60)

print("\n1. Removing old service...")
result = subprocess.run([sys.executable, 'service/wake_service_install.py', 'remove'], 
                       capture_output=True, text=True)
print(result.stdout if result.stdout else "[OK] Service removed")

print("\n2. Installing service with new code...")
result = subprocess.run([sys.executable, 'service/wake_service_install.py', 'install'], 
                       capture_output=True, text=True)
print(result.stdout if result.stdout else "[OK] Service installed")

print("\n3. Starting service...")
result = subprocess.run(['sc', 'start', 'StressTestWakeService'], 
                       capture_output=True, text=True)
if 'SUCCESS' in result.stdout or 'already been started' in result.stdout:
    print("[OK] Service started")
else:
    print(result.stdout)

# Wait for service to fully initialize
import time
print("Waiting for service to initialize...")
time.sleep()

print("\n" + "=" * 60)
print("SERVICE RESTART COMPLETE")
print("=" * 60)
print()

print("RUNNING DIAGNOSTICS...")
print("=" * 60)

# Check if task exists
print("\n1. Checking scheduled task...")
result = subprocess.run(['schtasks', '/query', '/tn', 'WakeFromS0_Service', '/v', '/fo', 'LIST'], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print("[OK] Task exists")
    # Look for last run time
    for line in result.stdout.split('\n'):
        if 'Last Run Time' in line or 'Next Run Time' in line or 'Status' in line:
            print(f"  {line.strip()}")
else:
    print("[ERROR] Task not found")

# Check power.json
print("\n2. Checking power.json...")
script_dir = os.path.dirname(os.path.abspath(__file__))
power_json = os.path.join(script_dir, 'data', 'power.json')
if os.path.exists(power_json):
    with open(power_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[OK] power.json exists")
    print(f"  Pending schedule: {data['current_state'].get('pending_wake_schedule')}")
    print(f"  Last wake: {data['current_state'].get('last_wake_time')}")
    print(f"  Wake history entries: {len(data.get('wake_history', []))}")
else:
    print("[ERROR] power.json not found")

# Check wake_complete.json
print("\n3. Checking wake_complete.json...")
wake_complete = os.path.join(script_dir, 'data', 'wake_complete.json')
if os.path.exists(wake_complete):
    with open(wake_complete, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[OK] wake_complete.json exists")
    print(f"  Content: {data}")
else:
    print("[WARN] wake_complete.json not found (created by wake_handler)")

# Check service status
print("\n4. Checking service status...")
result = subprocess.run(['sc', 'query', 'StressTestWakeService'], 
                       capture_output=True, text=True)
if 'RUNNING' in result.stdout:
    print("[OK] Service is RUNNING")
else:
    print("[ERROR] Service not running")
    print(result.stdout)
    
    # If service failed, check event log for error
    print("\n5. Checking Windows Event Log for service errors...")
    event_result = subprocess.run([
        'powershell', '-Command',
        "Get-EventLog -LogName Application -Source 'StressTestWakeService' -Newest 3 -ErrorAction SilentlyContinue | Select-Object -Property TimeGenerated, EntryType, Message | Format-List"
    ], capture_output=True, text=True)
    
    if event_result.stdout.strip():
        print(event_result.stdout)
    else:
        print("[INFO] No application errors found, checking system log...")
        sys_result = subprocess.run([
            'powershell', '-Command',
            "Get-EventLog -LogName System -Source 'Service Control Manager' -Newest 5 | Where-Object {$_.Message -like '*StressTestWakeService*'} | Select-Object -Property TimeGenerated, Message | Format-List"
        ], capture_output=True, text=True)
        print(sys_result.stdout if sys_result.stdout.strip() else "[INFO] No system errors found")

print("\n" + "=" * 60)
