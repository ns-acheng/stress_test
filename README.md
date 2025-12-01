# Windows Service Stress Test & Resource Monitor

This tool is designed to perform stress testing, resource monitoring, and stability checks on the Netskope Client (`stAgentSvc`) and Driver (`stadrv`) within a Windows environment. It simulates user activity (web browsing, network requests) while cycling service states and monitoring for crashes.

## Prerequisites

* **Operating System:** Windows 10, Windows 11, or Windows Server (64-bit recommended).
* **Python:** Python 3.6 or higher.
* **Permissions:** **Administrator privileges** are strictly required to control Windows services and access system debug privileges.

## Installation

1.  Ensure Python is added to your system PATH.
2.  Install the required dependencies using the provided requirements file:

```cmd
pip install -r requirement.txt
```

## Execution

1. Open **cmd.exe** with Administrator privileges and change the directory to the `stress_test` folder.

2. Configure proper values in `data\config.json` to match your testing requirements.

3. Run the script:
   ```cmd
   python.exe stress_test.py
   ```

4. Press ESC at any time to stop the test runs immediately.


## Config.json

`loop_times`: Total number of test iterations.

`stop_svc_interval`: Iteration frequency to stop/start the main service.

`stop_drv_interval`: Iteration frequency to restart the driver (nested within service stop).

`failclose_interval`: Iteration frequency to toggle FailClose settings.

`max_mem_usage`: System memory threshold (50-99%). If exceeded, browser tabs stop opening.

`max_tabs_open`: Maximum number of concurrent browser tabs allowed.

`custom_dump_path`: Dump path for external tools like **Windows Debug Diagnostic Tool**

* Strategy 1: Memory & Handle Leak Detection
```json
{
    "loop_times": 1000,
    "stop_svc_interval": 0,
    "stop_drv_interval": 0,
    "failclose_interval": 0,
    "max_mem_usage": 90,
    "max_tabs_open": 50,
    "custom_dump_path": ""
}
```

* Strategy 2: Application Crash Stress (User Mode)
```json
{
    "loop_times": 1000,
    "stop_svc_interval": 1,
    "stop_drv_interval": 0,
    "failclose_interval": 50,
    "max_mem_usage": 80,
    "max_tabs_open": 10,
    "custom_dump_path": ""
}
```

* Strategy 3: Memory & Handle Leak Detection
Hint: DO NOT restart the driver in each loop. 

```json
{
    "loop_times": 2000,
    "stop_svc_interval": 1,
    "stop_drv_interval": 10,
    "failclose_interval": 100,
    "max_mem_usage": 70,
    "max_tabs_open": 15,
    "custom_dump_path": ""
}
```





## Feature roadmap

1. Config changes for FailClose [done]
2. Steering mode changes
3. Crash dump monitoring and collection [done]
4. Estimate SYSTEM memory and CPU resource [done]
5. Collect 1000 URL and pick them randomnly to use [done]
6. Dynamic Steering changes
7. Network (NIC) changes
8. More network traffic type genarated by CURL and Python. [done]
9. Dynamic creating browser tabs and web traffic based on the memory usage. [done]
