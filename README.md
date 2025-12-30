# Windows Service Stress Test & Resource Monitor

This tool is designed to perform stress testing, resource monitoring, and stability checks on the Netskope Client (`stAgentSvc`) and Driver (`stadrv`) within a Windows environment. It simulates user activity (web browsing, network requests) while cycling service states and monitoring for crashes.

## Prerequisites

* **Operating System:** Windows 10, Windows 11, or Windows Server (64-bit recommended).
* **Python:** Python 3.6 or higher.
* **Permissions:** **Administrator privileges** are strictly required to control Windows services and access system debug privileges.
* **AOAC S0 (Optional):** To ensure the system wakes up from sleep, "Allow wake timers" must be enabled in Power Options -> Sleep -> Allow wake timers.

### Optional: Flooding Target Setup

If you plan to use the traffic generation features, set up the following targets:

1. **Firewall Rules**: Open necessary ports using PowerShell:
   ```powershell
   New-NetFirewallRule -DisplayName "Allow HTTP Stress Test" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
   New-NetFirewallRule -DisplayName "Allow UDP 8080 Stress Test" -Direction Inbound -Protocol UDP -LocalPort 8080 -Action Allow
   New-NetFirewallRule -DisplayName "Allow FTP Stress Test" -Direction Inbound -Protocol TCP -LocalPort 21 -Action Allow
   New-NetFirewallRule -DisplayName "Allow FTPS Stress Test" -Direction Inbound -Protocol TCP -LocalPort 990 -Action Allow
   New-NetFirewallRule -DisplayName "Allow SFTP Stress Test" -Direction Inbound -Protocol TCP -LocalPort 2222 -Action Allow
   ```

2. **HTTP Server (Port 80)**:
   ```cmd
   python -m http.server 80
   ```

3. **UDP Server (Port 8080)**:
   * Download `nc64.exe` from https://github.com/int0x33/nc.exe
   * Run:
     ```cmd
     nc64.exe -u -l -p 8080 -v
     ```

4. **FTP/FTPS Server**:
   * Make `C:\Program Files\Git\mingw64\bin` in SYSTEM Path variable.
   * Run:
     ```cmd
     python tool/run_ftp_server.py --port 21 --user test --password password
     python tool/run_ftp_server.py --port 990 --ftps --user test --password password
     ```
   * Supports "Blackhole" mode (discards uploads to save disk space).
   * FTPS mode auto-generates self-signed certificates.

5. **SFTP Server**:
   ```cmd
   python tool/run_sftp_server.py --port 2222 --user test --password password
   ```
   * Uses `paramiko` to run a stub SFTP server.

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

### Client Feature Toggling (client_feature_toggling)

This section controls various client state toggles. Each feature has an `enable` flag (1 for on, 0 for off).

#### FailClose (`failclose`)
*   `enable`: (0/1) Enable FailClose toggling.
*   `interval`: Iteration frequency to toggle FailClose settings.

#### Client Disabling (`client_disabling`)
*   `enable`: (0/1) If 1, runs a background thread that randomly enables/disables the client using `nsdiag`.
*   `enable_sec_min`: Minimum duration (seconds) to keep the client **ENABLED** before toggling (Valid: 180-600).
*   `enable_sec_max`: Maximum duration (seconds) to keep the client **ENABLED** before toggling (Valid: 600-1200).
*   `disable_ratio`: Ratio of disable duration relative to the enable duration (Valid: 0.0-1.0).
    *   *Example*: If enabled for 200s and ratio is 0.15, it will disable for 30s.

#### AOAC Sleep (`aoac_sleep`)
*   `enable`: (0/1) Enable system sleep triggers.
*   `interval`: Iteration frequency to trigger system sleep (S0 state).
*   `duration_sec`: Duration in seconds to stay in sleep mode before waking.

### Traffic Generation Settings (traffic_gen)

All traffic modules support `duration_sec` and `count`. If `duration_sec` > 0, it takes precedence over `count`.

#### Browser (`browser`)
*   `enable`: (0/1) If 1, enables the browser tab opening feature based on memory usage.
*   `max_memory`: System memory threshold (50-99%). If exceeded, browser tabs stop opening.
*   `max_tabs`: Maximum number of concurrent browser tabs allowed.

#### HTTPS Flood (`https`)
*   `enable`: (0/1) Enable HTTPS traffic generation using curl.
*   `duration_sec`: Duration to run the flood.
*   `count`: Number of requests (if duration is 0).
*   `concurrent_conn`: Number of concurrent threads.

#### DNS Flood (`dns`)
*   `enable`: (0/1) Enable random subdomain queries to bypass local DNS cache.
*   `duration_sec`: Duration to run the flood.
*   `count`: Number of queries (if duration is 0).
*   `concurrent_conn`: Number of concurrent threads.

#### FTP/FTPS/SFTP Traffic (`ftp`, `ftps`, `sftp`)
Each protocol has its own section in `config.json` with similar fields:
*   `enable`: (0/1) Enable traffic generation.
*   `target_ip`: Target server IP.
*   `target_port`: Target server port (Default: FTP 21, FTPS 990, SFTP 2222).
*   `user`: Username for authentication.
*   `password`: Password for authentication.
*   `file_size_mb`: Size of the file to upload in MB (generated in memory).
*   `duration_sec`: Duration to run the upload loop.
*   `count`: Number of uploads (if duration is 0).
*   `concurrent_conn`: Number of concurrent upload threads.

#### UDP Flood (`udp`)
*   `enable`: (0/1) Enable UDP packet flooding.
*   `duration_sec`: Duration to sustain the UDP flood.
*   `count`: Number of packets (if duration is 0).
*   `concurrent_conn`: Number of concurrent threads.
*   `target_ip`: Target IPv4 address.
*   `target_ipv6`: Target IPv6 address (Optional).
*   `target_port`: Target UDP port.

#### Apache Benchmark (`ab`)
*   `enable`: (0/1) Enable Apache Benchmark stress testing.
*   `duration_sec`: Duration to run the test.
*   `total_conn`: Total number of requests (if duration is 0).
*   `concurrent_conn`: Number of concurrent requests.
*   `target_urls`: List of URLs to target.

#### HTTPS Flood (`https`)
*   `enable`: (0/1) If 1, enables high-concurrency HTTP requests using curl.
*   `count`: (int) Total number of curl requests to send.
*   `duration_sec`: Duration to run the test.
*   `concurrent_conn`: (int) Number of concurrent curl processes.

`long_idle_interval`: Iteration frequency to trigger a long idle period (useful for soak testing). 
* If set to **> 0**: Sleeps for `long_idle_time_min` to `long_idle_time_max` seconds every N iterations.
* If set to **0**: Randomly sleeps for **30 to 120 seconds** in *every* iteration.

`long_idle_time_min`: Minimum duration for the long idle in seconds (Lower bound: 300s).

`long_idle_time_max`: Maximum duration for the long idle in seconds (Upper bound: 7200s).

**Strategy 1: Memory & Handle Leak Detection**
* * The main idea is NOT to stop client service and keep it running but open/close the browser tabs.
* * Then check the resource usage.
 
```json
{
    "loop_times": 3000,
    "stop_svc_interval": 0,
    "stop_drv_interval": 0,
    "client_feature_toggling": {
        "failclose": { "enable": 0, "interval": 0 },
        "client_disabling": { "enable": 0 },
        "aoac_sleep": { "enable": 0, "interval": 0, "duration_sec": 60 }
    },
    "custom_dump_path": "",
    "traffic_gen": {
        "browser": {
            "enable": 1,
            "max_memory": 90,
            "max_tabs": 50
        }
    }
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
    "client_feature_toggling": {
        "failclose": { "enable": 1, "interval": 50 },
        "client_disabling": { "enable": 0 },
        "aoac_sleep": { "enable": 0, "interval": 0, "duration_sec": 60 }
    },
    "custom_dump_path": "",
    "long_idle_interval": 0,
    "long_idle_time_min": 300,
    "long_idle_time_max": 300,
    "traffic_gen": {
        "browser": {
            "enable": 1,
            "max_memory": 80,
            "max_tabs": 30
        }
    }
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
    "client_feature_toggling": {
        "failclose": { "enable": 1, "interval": 50 },
        "client_disabling": { "enable": 0 },
        "aoac_sleep": { "enable": 0, "interval": 0, "duration_sec": 60 }
    },
    "custom_dump_path": "",
    "long_idle_interval": 0,
    "long_idle_time_min": 300,
    "long_idle_time_max": 300,
    "traffic_gen": {
        "browser": {
            "enable": 1,
            "max_memory": 80,
            "max_tabs": 30
        }
    }
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
    "client_feature_toggling": {
        "failclose": { "enable": 1, "interval": 100 },
        "client_disabling": { "enable": 0 },
        "aoac_sleep": { "enable": 1, "interval": 1, "duration_sec": 60 }
    },
    "custom_dump_path": "",
    "long_idle_interval": 1,
    "long_idle_time_min": 1000,
    "long_idle_time_max": 3600,
    "traffic_gen": {
        "browser": {
            "enable": 1,
            "max_memory": 60,
            "max_tabs": 10
        }
    }
}
```


**Strategy 5: High Concurrency / Traffic Stress**
* * Uses internal Python generators for DNS/UDP and ab.exe for TCP connections.
* * If you do not use a real HTTP server, keep `ab` -> `concurrent_conn` lower then 500.

```json
{
  "loop_times": 1000,
  "stop_svc_interval": 5,
  "stop_drv_interval": 0,
  "client_feature_toggling": {
    "failclose": {
      "enable": 1,
      "interval": 15
    },
    "client_disabling": {
      "enable": 0,
      "enable_sec_min": 180,
      "enable_sec_max": 600,
      "disable_ratio": 0.15
    },
    "aoac_sleep": {
      "enable": 0,
      "interval": 0,
      "duration_sec": 60
    }
  },
  "custom_dump_path": "C:\\dump\\stAgentSvc.exe\\*.dmp",
  "long_idle_interval": 100,
  "long_idle_time_min": 300,
  "long_idle_time_max": 600,
  "traffic_gen": {
    "browser": {
      "enable": 1,
      "max_memory": 60,
      "max_tabs": 20
    },
    "dns": {
      "enable": 1,
      "count": 500,
      "duration_sec": 0,
      "concurrent_conn": 20
    },
    "udp": {
      "enable": 1,
      "target_ip": "192.168.1.2",
      "target_ipv6": "",
      "target_port": 8080,
      "duration_sec": 20,
      "count": 0,
      "concurrent_conn": 10
    },
    "ab": {
      "enable": 1,
      "total_conn": 10000,
      "concurrent_conn": 256,
      "duration_sec": 0,
      "target_urls": [
        "http://10.1.2.3"
      ]
    },
    "https": {
      "enable": 1,
      "count": 1000,
      "duration_sec": 0,
      "concurrent_conn": 50
    }
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
7. **Traffic Generation**: Dynamic creating browser tabs based on memory usage.
8. **Traffic Generation**: Massive traffic generation (DNS, UDP, FTP, FTPS, SFTP).
9. **Traffic Generation**: High-volume HTTP/HTTPS flood support (via Curl).
10. **Traffic Generation**: High concurrency connection testing (via Apache Bench).
11. **Simulation**: Block host to simulate FailClose.
12. **Simulation**: Network (NIC) enabling/disabling.
13. **Simulation**: System Sleep (S0) simulation.
14. **Simulation**: Client Enable/Disable toggling via `nsdiag`.
15. **Diagnostics**: Auto-collect log bundle (`nsdiag`) and dump files upon crash detection.
