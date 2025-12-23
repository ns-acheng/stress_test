# Windows Service Stress Test & Resource Monitor

This tool is designed to perform stress testing, resource monitoring, and stability checks on the Netskope Client (`stAgentSvc`) and Driver (`stadrv`) within a Windows environment. It simulates user activity (web browsing, network requests) while cycling service states and monitoring for crashes.

## Prerequisites

* **Operating System:** Windows 10, Windows 11, or Windows Server (64-bit recommended).
* **Python:** Python 3.6 or higher.
* **Permissions:** **Administrator privileges** are strictly required to control Windows services and access system debug privileges.
* **Flooding target (Optional):**
    * use the powersheel command to open the 80 and 8080 port
      
       ```powershell
       New-NetFirewallRule -DisplayName "Allow HTTP Stress Test" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
       New-NetFirewallRule -DisplayName "Allow UDP 8080 Stress Test" -Direction Inbound -Protocol UDP -LocalPort 8080 -Action Allow
       ```
  
    * run HTTP server in 80 port
       ```cmd
       python -m http.server 80
       ```
  
    * download `nc64.exe` from https://github.com/int0x33/nc.exe
    * run `nc64.exe`
       ```cmd
       nc64.exe -u -l -p 8080 -v
       ```

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

`disable_client`: (0/1) If 1, runs a background thread that randomly enables/disables the client using `nsdiag`.

`max_mem_usage`: System memory threshold (50-99%). If exceeded, browser tabs stop opening.

`max_tabs_open`: Maximum number of concurrent browser tabs allowed.

`custom_dump_path`: Dump path for external tools like **Windows Debug Diagnostic Tool**

`system_sleep_interval`: Iteration frequency to trigger system sleep (S0 state). Set to 0 to disable.

`system_sleep_seconds`: Duration in seconds to stay in sleep mode before waking.

`long_idle_interval`: Iteration frequency to trigger a long idle period (useful for soak testing). 
* If set to **> 0**: Sleeps for `long_idle_time_min` to `long_idle_time_max` seconds every N iterations.
* If set to **0**: Randomly sleeps for **30 to 120 seconds** in *every* iteration.

`long_idle_time_min`: Minimum duration for the long idle in seconds (Lower bound: 300s).

`long_idle_time_max`: Maximum duration for the long idle in seconds (Upper bound: 7200s).

### Traffic Generation Settings (traffic_gen)
`dns_flood_enabled`: (0/1) If 1, generates random subdomain queries to bypass local DNS cache.

`dns_query_count`: (int) Number of random DNS queries to generate per iteration (default: 500).

`udp_flood_enabled`: (0/1) If 1, sends UDP packets to target. (Note: Automatically toggles between IPv6 and IPv4 on alternate iterations if IPv6 is configured).

`udp_target_ip`: (str) Target IPv4 address for UDP flood.

`udp_target_ipv6`: (str) Target IPv6 address for UDP flood (Optional).

`udp_target_port`: (int) Target UDP port (default: 8080).

`udp_duration_seconds`: (int/float) Duration in seconds to sustain the UDP flood per iteration (default: 10).

`ab_total_conn`: (int) Total number of requests to perform for Apache Bench.

`ab_concurrent_conn`: (int) Target number of concurrent connections for Apache Bench. Set to 0 to disable.

`ab_urls`: (list[str]) List of target URLs for Apache Bench. The test cycles through these URLs one by one per iteration.

`curl_flood_enabled`: (0/1) If 1, enables high-concurrency HTTP requests using curl.

`curl_flood_count`: (int) Total number of curl requests to send.

`curl_flood_concurrency`: (int) Number of concurrent curl processes.


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
    "long_idle_interval": 0,
    "long_idle_time_min": 300,
    "long_idle_time_max": 300,
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
    "long_idle_interval": 0,
    "long_idle_time_min": 300,
    "long_idle_time_max": 300
}
```

**Strategy 4: Soak Mode**
* * With very limited resource using for a long term with longer sleep time.
* * So we give a big loop_times and longer `long_idle_time`.

```json
{

    "loop_times": 9000,
    "stop_svc_interval": 0,
    "stop_drv_interval": 0,
    "failclose_interval": 100,
    "max_mem_usage": 60,
    "max_tabs_open": 10,
    "custom_dump_path": "",
    "long_idle_interval": 1,
    "long_idle_time_min": 1000,
    "long_idle_time_max": 3600
}
```


**Strategy 5: High Concurrency / Traffic Stress**
* * Uses internal Python generators for DNS/UDP and ab.exe for TCP connections.
* * If you do not use a real HTTP server, keep `ab_concurrent_conn` lower then 500.

```json
{
  "loop_times": 1000,
  "stop_svc_interval": 5,
  "stop_drv_interval": 0,
  "failclose_interval": 15,
  "max_mem_usage": 60,
  "max_tabs_open": 20,
  "custom_dump_path": "C:\\dump\\stAgentSvc.exe\\*.dmp",
  "long_idle_interval": 100,
  "long_idle_time_min": 300,
  "long_idle_time_max": 600,
  "traffic_gen": {
    "dns_flood_enabled": 1,
    "dns_query_count": 500,
    "udp_flood_enabled": 1,
    "udp_target_ip": "192.168.1.2",
    "udp_target_ipv6": "",
    "udp_target_port": 8080,
    "udp_duration_seconds": 20,
    "ab_total_conn": 10000,
    "ab_concurrent_conn": 256,
    "ab_urls": [
      "http://10.1.2.3"
    ],
    "curl_flood_enabled": 1,
    "curl_flood_count": 1000,
    "curl_flood_concurrency": 50
  }
}
```

## Feature roadmap

1. Reboot and task scheduler to restart the tool
2. Steering mode changes
3. Dynamic Steering changes
4. Periodically stAgentSvc resource check


## Features done

1. Config changes for FailClose
2. Crash dump monitoring and collection
3. **Service Hang Detection**: Auto-detects if service fails to stop, generates a Live Dump, and collects logs.
4. Estimate SYSTEM memory and CPU resource
5. Collect ~12,000 URLs and pick them randomly to use
6. More network traffic type generated by CURL and Python.
7. Dynamic creating browser tabs and web traffic based on the memory usage.
8. Block host to simulate FailClose
9. Network (NIC) changes
10. Massive DNS/UDP traffic generation
11. High concurrency connection testing (via Apache Bench) with multi-URL support
12. Auto-collect log bundle (`nsdiag`) and dump files upon crash detection
13. System Sleep (S0) simulation
14. Client Enable/Disable toggling via `nsdiag`
15. Curl-based HTTP flood support