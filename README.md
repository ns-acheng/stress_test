# Windows Service Stress Test & Resource Monitor

This tool is designed to perform stress testing, resource monitoring, and stability checks on the Netskope Client (`stAgentSvc`) and Driver (`stadrv`) within a Windows environment. It simulates user activity (web browsing, network requests) while cycling service states and monitoring for crashes.

## Prerequisites

* **Operating System:** Windows 10, Windows 11, or Windows Server (64-bit recommended).
* **Python:** Python 3.6 or higher.
* **Permissions:** **Administrator privileges** are strictly required to control Windows services and access system debug privileges.
* **External Tools (Optional):**
    * **Apache Bench (`ab.exe`):** Required for high-concurrency connection testing. Download the Apache binaries for Windows (e.g., from Apache Lounge), extract the contents, and place `ab.exe` inside the `tool/ab/` directory.

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

`stop_svc_interval`: Iteration frequency to stop/start the main service. Set to 0 to disable.

`stop_drv_interval`: Iteration frequency to restart the driver (nested within service stop). Set to 0 to disable.

`failclose_interval`: Iteration frequency to toggle FailClose settings. Set to 0 to disable.

`max_mem_usage`: System memory threshold (50-99%). If exceeded, browser tabs stop opening.

`max_tabs_open`: Maximum number of concurrent browser tabs allowed.

`custom_dump_path`: Dump path for external tools like **Windows Debug Diagnostic Tool**

`long_sleep_interval`: Iteration frequency to trigger a long sleep period (useful for soak testing). Set to 0 to disable. In each iteration, it randomly sleep for `long_sleep_time_min` to `long_sleep_time_max`.

`long_sleep_time_min`: Minimum duration for the long sleep in seconds (Lower bound: 300s).

`long_sleep_time_max`: Maximum duration for the long sleep in seconds (Upper bound: 7200s).



**Strategy 1: Memory & Handle Leak Detection**
* * The main idea is NOT to stop client service and keep it running but open/close the browser tabs.
* * Then check the resource usage.
 
```json
{
    "loop_times": 3000,
    "stop_svc_interval": 0,
    "stop_drv_interval": 0,
    "failclose_interval": 0,
    "max_mem_usage": 90,
    "max_tabs_open": 50,
    "custom_dump_path": "",
    "long_sleep_interval": 100,
    "long_sleep_time_min": 300,
    "long_sleep_time_max": 600
}
```


**Strategy 2: Application Crash Stress (User Mode)**
* * The main idea is to stop the user mode service `stAgentSvc` in each iteration.
* * As different feature flags are enabled, we can know more about the stability of certian features.


```json
{
    "loop_times": 1000,
    "stop_svc_interval": 1,
    "stop_drv_interval": 0,
    "failclose_interval": 50,
    "max_mem_usage": 80,
    "max_tabs_open": 30,
    "custom_dump_path": "",
    "long_sleep_interval": 0,
    "long_sleep_time_min": 300,
    "long_sleep_time_max": 300
}
```

**Strategy 3: Blue Screen Detection**
* * Try to stop the driver every few iterations and see of BSOD occurs.
* * If it happens, please collect C:\Windows\memory.dmp

* * Hint: DO NOT restart the driver in each loop. 

```json
{

    "loop_times": 1000,
    "stop_svc_interval": 1,
    "stop_drv_interval": 1,
    "failclose_interval": 50,
    "max_mem_usage": 80,
    "max_tabs_open": 30,
    "custom_dump_path": "",
    "long_sleep_interval": 0,
    "long_sleep_time_min": 300,
    "long_sleep_time_max": 300
}
```

**Strategy 4: Soak Mode**
* * With very limited resource using for a long term with longer sleep time.
* * So we give a big loop_times and longer `long_sleep_time`.

```json
{

    "loop_times": 9000,
    "stop_svc_interval": 0,
    "stop_drv_interval": 0,
    "failclose_interval": 100,
    "max_mem_usage": 60,
    "max_tabs_open": 10,
    "custom_dump_path": "",
    "long_sleep_interval": 1,
    "long_sleep_time_min": 1000,
    "long_sleep_time_max": 3600
}
```



## Feature roadmap

1. Reboot and task scheduler to restart the tool
2. Collect the log bundle if any error is found
3. Steering mode changes
4. Dynamic Steering changes
5. Perically stAgentSvc resource check




## Features done

1. Config changes for FailClose
2. Crash dump monitoring and collection
3. Estimate SYSTEM memory and CPU resource
4. Collect 2000 URL and pick them randomnly to use
5. More network traffic type genarated by CURL and Python.
6. Dynamic creating browser tabs and web traffic based on the memory usage.
7. Block host to simulate FailClose
8. Network (NIC) changes
