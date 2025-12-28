"""
Windows Service for S0 Modern Standby Wake Timer Management

This service runs continuously in Session 0 and manages wake timers
for S0 Modern Standby sleep/wake cycles. It survives system sleep
and coordinates with Task Scheduler for reliable wake operations.
"""

import win32serviceutil
import win32service
import win32event
import servicemanager
import win32com.client
import pythoncom
import time
import json
import os
import sys
from datetime import datetime, timedelta
import threading
import logging

# Service configuration
SERVICE_NAME = "StressTestWakeService"
SERVICE_DISPLAY_NAME = "Stress Test Wake Service"
SERVICE_DESCRIPTION = "Manages S0 Modern Standby wake timers for stress testing"

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'log')
POWER_JSON = os.path.join(DATA_DIR, 'power.json')
SERVICE_LOG = os.path.join(LOG_DIR, 'wake_service.log')

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


class WakeService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        
        # Setup logging
        logging.basicConfig(
            filename=SERVICE_LOG,
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('WakeService')
        
        # Initialize power.json
        self.init_power_json()
        
    def init_power_json(self):
        """Initialize power.json with default structure if not exists."""
        if not os.path.exists(POWER_JSON):
            default_data = {
                "service_config": {
                    "service_name": SERVICE_NAME,
                    "log_level": "INFO",
                    "max_history_entries": 100,
                    "version": "1.0"
                },
                "current_state": {
                    "service_running": False,
                    "last_wake_time": None,
                    "pending_wake_schedule": None,
                    "last_error": None
                },
                "wake_schedule": None,
                "wake_history": []
            }
            self.write_power_json(default_data)
    
    def read_power_json(self):
        """Read power.json with error handling."""
        try:
            if os.path.exists(POWER_JSON):
                with open(POWER_JSON, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading power.json: {e}")
        return None
    
    def write_power_json(self, data):
        """Write power.json with error handling."""
        try:
            with open(POWER_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error writing power.json: {e}")
    
    def update_service_state(self, **kwargs):
        """Update current_state in power.json."""
        data = self.read_power_json()
        if data:
            data['current_state'].update(kwargs)
            self.write_power_json(data)
    
    def SvcStop(self):
        """Stop the service."""
        self.logger.info('Service stop requested')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False
        self.update_service_state(service_running=False)
    
    def SvcDoRun(self):
        """Main service loop."""
        # Report service is starting
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        
        self.logger.info('Service started')
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        self.update_service_state(service_running=True)
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_wake_requests)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Main service loop - wait for stop event
        while self.running:
            rc = win32event.WaitForSingleObject(self.stop_event, 1000)
            if rc == win32event.WAIT_OBJECT_0:
                break
        
        self.logger.info('Service stopped')
    
    def monitor_wake_requests(self):
        """Monitor power.json for wake schedule requests."""
        self.logger.info('Wake request monitor started')
        last_check = None
        check_count = 0
        
        while self.running:
            try:
                data = self.read_power_json()
                if not data:
                    time.sleep(1)
                    continue
                
                schedule = data.get('wake_schedule')
                
                # Check if there's a new wake schedule request
                if schedule and schedule != last_check:
                    self.logger.info(f"New wake schedule detected: {schedule}")
                    last_check = schedule
                    check_count = 0
                    
                    # Process the wake schedule
                    success = self.process_wake_schedule(schedule)
                    
                    if success:
                        # Update state to show schedule is active
                        self.update_service_state(
                            pending_wake_schedule=schedule,
                            last_error=None
                        )
                    else:
                        self.update_service_state(
                            pending_wake_schedule=None,
                            last_error="Failed to create wake timer"
                        )
                
                # Check for wake completion
                if data['current_state'].get('pending_wake_schedule'):
                    self.check_wake_completion()
                
                # Periodic logging to show service is alive
                check_count += 1
                if check_count % 300 == 0:  # Every 5 minutes
                    self.logger.info(f"Service monitoring - checks: {check_count}")
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)
    
    def process_wake_schedule(self, schedule):
        """Create Task Scheduler task with wake timer."""
        try:
            task_name = schedule.get('task_name', 'WakeFromS0_Service')
            duration = schedule.get('duration_seconds', 10)
            
            self.logger.info(f"Creating wake task '{task_name}' for {duration}s")
            
            # Initialize COM for this thread
            pythoncom.CoInitialize()
            
            try:
                # Connect to Task Scheduler
                scheduler = win32com.client.Dispatch('Schedule.Service')
                scheduler.Connect()
                root_folder = scheduler.GetFolder('\\')
                
                # Delete existing task if present
                try:
                    root_folder.DeleteTask(task_name, 0)
                    self.logger.info(f"Deleted existing task: {task_name}")
                except:
                    pass
                
                # Create new task definition
                task_def = scheduler.NewTask(0)
                task_def.RegistrationInfo.Description = 'S0 Wake Timer - Stress Test Service'
                task_def.RegistrationInfo.Author = 'StressTestWakeService'
                
                # Set principal - run as SYSTEM account (works on any machine)
                task_def.Principal.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST
                task_def.Principal.UserId = 'SYSTEM'
                task_def.Principal.LogonType = 5  # TASK_LOGON_SERVICE_ACCOUNT
                
                # Configure settings
                task_def.Settings.Enabled = True
                task_def.Settings.StopIfGoingOnBatteries = False
                task_def.Settings.DisallowStartIfOnBatteries = False
                task_def.Settings.AllowDemandStart = True
                task_def.Settings.WakeToRun = True  # CRITICAL: Enable wake timer
                
                # Create time-based trigger
                trigger_time = datetime.now() + timedelta(seconds=duration)
                trigger = task_def.Triggers.Create(1)  # TASK_TRIGGER_TIME
                trigger.StartBoundary = trigger_time.strftime('%Y-%m-%dT%H:%M:%S')
                trigger.Enabled = True
                
                self.logger.info(f"Wake trigger set for: {trigger_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Create action - run wake handler script
                action = task_def.Actions.Create(0)  # TASK_ACTION_EXEC
                wake_handler = os.path.join(os.path.dirname(__file__), 'wake_handler.py')
                action.Path = 'python'
                action.Arguments = f'"{wake_handler}"'
                
                # Register the task with SYSTEM account
                root_folder.RegisterTaskDefinition(
                    task_name,
                    task_def,
                    6,  # TASK_CREATE_OR_UPDATE
                    '',  # Empty string = use Principal.UserId (SYSTEM)
                    '',  # No password needed
                    5    # TASK_LOGON_SERVICE_ACCOUNT
                )
                
                self.logger.info(f"Wake task '{task_name}' created successfully")
                return True
                
            finally:
                pythoncom.CoUninitialize()
                
        except Exception as e:
            self.logger.error(f"Error creating wake task: {e}")
            return False
    
    def check_wake_completion(self):
        """Check if scheduled wake has completed."""
        try:
            data = self.read_power_json()
            if not data:
                return
            
            schedule = data['current_state'].get('pending_wake_schedule')
            if not schedule:
                return
            
            # Check if wake_handler.py has written completion
            wake_completion_file = os.path.join(DATA_DIR, 'wake_complete.json')
            if os.path.exists(wake_completion_file):
                try:
                    with open(wake_completion_file, 'r', encoding='utf-8') as f:
                        completion_data = json.load(f)
                    
                    # Add to wake history
                    data['wake_history'].append(completion_data)
                    
                    # Limit history size
                    max_entries = data['service_config'].get('max_history_entries', 100)
                    if len(data['wake_history']) > max_entries:
                        data['wake_history'] = data['wake_history'][-max_entries:]
                    
                    # Update state
                    data['current_state']['last_wake_time'] = completion_data.get('wake_time')
                    data['current_state']['pending_wake_schedule'] = None
                    data['wake_schedule'] = None
                    
                    self.write_power_json(data)
                    
                    # Clean up completion file
                    os.remove(wake_completion_file)
                    
                    self.logger.info(f"Wake completed: {completion_data}")
                    
                    # Clean up scheduled task
                    self.cleanup_wake_task(schedule.get('task_name', 'WakeFromS0_Service'))
                    
                except Exception as e:
                    self.logger.error(f"Error processing wake completion: {e}")
        
        except Exception as e:
            self.logger.error(f"Error checking wake completion: {e}")
    
    def cleanup_wake_task(self, task_name):
        """Delete scheduled task after completion."""
        try:
            pythoncom.CoInitialize()
            try:
                scheduler = win32com.client.Dispatch('Schedule.Service')
                scheduler.Connect()
                root_folder = scheduler.GetFolder('\\')
                root_folder.DeleteTask(task_name, 0)
                self.logger.info(f"Cleaned up task: {task_name}")
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            self.logger.error(f"Error cleaning up task: {e}")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WakeService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(WakeService)
