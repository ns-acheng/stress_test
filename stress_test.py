import sys
import os
import random
import threading
from util_service import start_service, stop_service, get_service_status
from util_log import LogSetup
from util_time import smart_sleep
from util_subprocess import (
    run_batch, 
    run_powershell, 
    nsdiag_update_config,
    run_curl
)
from util_resources import (
    get_system_memory_usage, 
    log_resource_usage, 
    enable_debug_privilege
)
from util_network import check_url_alive
from util_input import start_input_monitor
from util_crash import check_crash_dumps, crash_handle
from util_config import AgentConfigManager
from util_tool_config import ToolConfig
import util_traffic 

TINY_SEC = 5
SHORT_SEC = 15
STD_SEC = 30
LONG_SEC = 60
BATCH_LIMIT = 30

try:
    log_helper = LogSetup()
    logger = log_helper.setup_logging()
    current_timestamp = log_helper.get_timestamp()
    current_log_dir = log_helper.get_log_folder()
except Exception as e:
    print(f"Critical error during logging setup: {e}", file=sys.stderr)
    sys.exit(1)

class StressTest:
    def __init__(self):
        self.service_name = "stagentsvc"
        self.drv_name = "stadrv"
        self.url_file = r"data\url.txt"
        self.tool_dir = "tool"
        
        self.cfg_mgr = AgentConfigManager()
        self.config = ToolConfig(r"data\config.json")
        self.stop_event = threading.Event()
        
        self.urls = []
        self.manage_nic_script = os.path.join(self.tool_dir, "manage_nic.ps1")
        self.total_zero_dumps = 0

    def setup(self):
        enable_debug_privilege()
        self.config.load()
        self.load_urls()
        
        self.cfg_mgr.setup_environment()
        self.cfg_mgr.restore_config(remove_only=True)

    def tear_down(self):
        self.cfg_mgr.restore_config()

        if os.path.exists(self.manage_nic_script):
            logger.info("Tear down: Ensuring NICs are enabled...")
            run_powershell(self.manage_nic_script, ["-Action", "Enable"])

    def load_urls(self):
        try:
            if not os.path.exists(self.url_file):
                logger.error(f"{self.url_file} not found.")
                return

            with open(self.url_file, 'r') as f:
                lines = f.readlines()
            
            self.urls = [line.strip() for line in lines if line.strip()]
            logger.info(f"Loaded {len(self.urls)} URLs from {self.url_file}")
            
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")

    def exec_failclose_check(self):
        if not os.path.exists(self.manage_nic_script):
            logger.error(f"NIC Manager script not found: {self.manage_nic_script}")
            return

        logger.info("Simulating FailClose by Disabling NICs...")
        run_powershell(self.manage_nic_script, ["-Action", "Disable"])

        if smart_sleep(SHORT_SEC, self.stop_event):
            return

        test_urls = random.sample(self.urls, min(len(self.urls), 10))
        logger.info(f"Checking {len(test_urls)} URLs for reachability...")

        for url in test_urls:
            if self.stop_event.is_set(): break
            alive = check_url_alive(url)
            status = "ALIVE" if alive else "DEAD (Blocked)"
            logger.info(f"URL: {url} -> {status}")
            if smart_sleep(1, self.stop_event):
                break

        logger.info("FailClose check done. Re-Enabling NICs...")
        run_powershell(self.manage_nic_script, ["-Action", "Enable"])
        
        smart_sleep(SHORT_SEC, self.stop_event)

    def header_msg(self):
        logger.info(f"--- Start. Total iterations: {self.config.loop_times} ---")
        logger.info(f"Stop service interval: {self.config.stop_svc_interval}")
        logger.info(f"Switch FailClose interval: {self.config.failclose_interval}")
        logger.info(f"Stop/Start driver interval: {self.config.stop_drv_interval}")
        logger.info(f"Max Memory Threshold: {self.config.max_mem_usage}%")
        logger.info(f"Max Tabs Open: {self.config.max_tabs_open}")
        if self.config.long_sleep_interval > 0:
            logger.info(f"Long Sleep Interval: {self.config.long_sleep_interval}")
            logger.info(
                f"Long Sleep Time: {self.config.long_sleep_time_min} - "
                f"{self.config.long_sleep_time_max} sec"
            )
        else:
            logger.info("Long Sleep Interval is 0. Random sleep 30-120s enabled.")

        if self.config.custom_dump_path:
            logger.info(f"Custom Dump Path: {self.config.custom_dump_path}")
        logger.info(f"Log Folder: {current_log_dir}")
        logger.info("--> Press ESC or Ctrl+C to stop the test immediately. <--")
        logger.info("=" * 50)

    def exec_start_service(self):
        status = get_service_status(self.service_name)
        if status == "NOT_FOUND":
            logger.error(f"Service {self.service_name} NOT FOUND. Stopping...")
            self.stop_event.set()
            return

        logger.info(f"Current status: {status}")
        if status != "RUNNING":
            start_service(self.service_name)
            logger.info(f"Waiting for {STD_SEC} seconds")
            if smart_sleep(STD_SEC, self.stop_event): 
                return
        log_resource_usage(
            "stAgentSvc.exe", current_log_dir
        )

    def exec_stop_service(self):
        status = get_service_status(self.service_name)
        if status == "NOT_FOUND":
            logger.error(f"Service {self.service_name} NOT FOUND. Stopping...")
            self.stop_event.set()
            return

        logger.info(f"Current status: {status}")
        if status == "RUNNING":
            log_resource_usage(
                "stAgentSvc.exe", current_log_dir
            )
            stop_service(self.service_name)
            self.cur_svc_status = get_service_status(self.service_name)
            logger.info(f"Current status: {self.cur_svc_status}")
            if smart_sleep(TINY_SEC, self.stop_event): 
                return

    def exec_restart_driver(self):
        if get_service_status(self.drv_name) == "NOT_FOUND":
            logger.error(f"Driver {self.drv_name} NOT FOUND. Stopping...")
            self.stop_event.set()
            return
            
        logger.info(f"To STOP and START driver 'stadrv'")
        stop_service(self.drv_name)
        status = get_service_status(self.service_name)
        logger.info(f"Current status: {status}")
        if smart_sleep(SHORT_SEC, self.stop_event): 
            return
        start_service(self.drv_name)
        if smart_sleep(TINY_SEC, self.stop_event): 
            return
    
    def exec_browser_tabs(self):
        if not self.urls:
            logger.warning("No URLs loaded to open.")
            return

        logger.info(
            f"Start tab loop. Max Mem: {self.config.max_mem_usage}%, "
            f"Max Tabs: {self.config.max_tabs_open}"
        )
        
        batch_cnt = 0
        total_tabs = 0

        while batch_cnt < BATCH_LIMIT:
            if self.stop_event.is_set(): 
                break
            if total_tabs >= self.config.max_tabs_open:
                logger.info(f"Max tabs reached ({total_tabs}). Stop opening.")
                break

            remaining = self.config.max_tabs_open - total_tabs
            count = min(len(self.urls), 10)
            count = min(count, remaining)

            if count <= 0:
                break

            selected_urls = random.sample(self.urls, count)
            logger.info(
                f"Opening batch {batch_cnt + 1} ({count} URLs)..."
            )
            
            args = " ".join(selected_urls)
            cmd = os.path.join(self.tool_dir, f"open_msedge_tabs.bat {args}")
            run_batch(cmd)
            
            total_tabs += count
            if smart_sleep(STD_SEC, self.stop_event): 
                break
            log_resource_usage(
                "stAgentSvc.exe", current_log_dir
            )

            mem_usage = get_system_memory_usage()
            mem_pct = mem_usage * 100.0   
            logger.info(
                f"System Memory: {mem_pct:.2f}% (Target: {self.config.max_mem_usage}%)"
            )

            if mem_pct >= self.config.max_mem_usage:
                logger.info(
                    f"Threshold reached ({mem_pct:.2f}% >= {self.config.max_mem_usage}%)."
                )
                break

            batch_cnt += 1

        if batch_cnt >= BATCH_LIMIT:
            logger.warning(f"Reached maximum batch limit ({BATCH_LIMIT})")

    def exec_curl_requests(self):
        if not self.urls:
            return

        count = min(len(self.urls), 10)
        selected_urls = random.sample(self.urls, count)
        logger.info(f"Running CURL on {count} random URLs...")
        
        for url in selected_urls:
            if self.stop_event.is_set(): 
                break
            run_curl(url)
            logger.info(f"CURL with URL: {url}")

    def run(self):
        start_input_monitor(self.stop_event)

        self.header_msg()

        count = 0
        for count in range(1, self.config.loop_times + 1):
            if self.stop_event.is_set(): 
                break
            try:
                logger.info(f"==== Iteration {count} / {self.config.loop_times} ====")
                
                self.exec_start_service()
                if self.stop_event.is_set(): break

                if not self.cfg_mgr.is_local_cfg:
                    nsdiag_update_config(self.cfg_mgr.is_64bit)
                else:
                    logger.info("Local config active, skip nsdiag update")

                if self.stop_event.is_set(): break

                if self.config.traffic_dns_enabled:
                    total_dns = self.config.traffic_dns_count
                    logger.info(f"Starting DNS Flood: {total_dns} queries planned.")
                    
                    if self.urls:
                        sample_k = min(len(self.urls), 10)
                        samples = random.sample(self.urls, sample_k)
                        logger.info(f"Sample targets ({sample_k} of {len(self.urls)} loaded):")
                        for s in samples:
                            logger.info(f"  {s}")
                    
                    util_traffic.generate_dns_flood(
                        self.urls, 
                        self.config.traffic_dns_count
                    )
                
                if self.config.traffic_udp_enabled:
                    current_target = self.config.udp_target_ip
                    use_ipv6 = False

                    if self.config.udp_target_ipv6:
                        if count % 2 == 0:
                            current_target = self.config.udp_target_ipv6
                            use_ipv6 = True
                        else:
                            current_target = self.config.udp_target_ip
                            use_ipv6 = False

                    util_traffic.generate_udp_flood(
                        current_target, 
                        self.config.udp_target_port, 
                        float(self.config.traffic_udp_duration), 
                        self.stop_event, 
                        use_ipv6
                    )
                
                if self.config.ab_concurrent_conn > 0 and self.config.ab_urls:
                    idx = count % len(self.config.ab_urls)
                    current_ab_url = self.config.ab_urls[idx]
                    
                    util_traffic.run_high_concurrency_test(
                        current_ab_url,
                        10000, 
                        self.config.ab_concurrent_conn,
                        self.tool_dir,
                        self.stop_event
                    )

                if self.stop_event.is_set(): break

                if self.cfg_mgr.is_false_close:
                    self.exec_failclose_check()
                else:
                    self.exec_browser_tabs()
                    self.exec_curl_requests()

                if self.stop_event.is_set(): break

                if self.config.stop_svc_interval > 0:
                    if count % self.config.stop_svc_interval == 0:
                        self.exec_stop_service()
                        if self.stop_event.is_set(): break

                        if self.config.stop_drv_interval > 0:
                            if count % self.config.stop_drv_interval == 0:
                                self.exec_restart_driver()
                                if self.stop_event.is_set(): break

                        if self.config.failclose_interval > 0:
                            if count % self.config.failclose_interval == 0:
                                self.cfg_mgr.toggle_failclose()
                                if self.stop_event.is_set(): break

                if self.config.long_sleep_interval == 0:
                    sleep_dur = random.randint(30, 120)
                    logger.info(
                        f"Random Sleep triggered (long_sleep_interval=0). "
                        f"Sleeping {sleep_dur}s..."
                    )
                    if smart_sleep(sleep_dur, self.stop_event):
                        break

                if self.config.long_sleep_interval > 0:
                    if count % self.config.long_sleep_interval == 0:
                        sleep_dur = random.randint(
                            self.config.long_sleep_time_min, 
                            self.config.long_sleep_time_max
                        )
                        logger.info(
                            f"Long Sleep triggered. Sleeping {sleep_dur}s..."
                        )
                        if smart_sleep(sleep_dur, self.stop_event): 
                            break

                ps_script = os.path.join(self.tool_dir, "close_browsers.ps1")
                run_powershell(ps_script)
                if smart_sleep(SHORT_SEC, self.stop_event): 
                    break

                crash_found, zero_count = check_crash_dumps(self.config.custom_dump_path)
                self.total_zero_dumps += zero_count
                
                if zero_count > 0:
                    logger.info(f"Cleaned {zero_count} 0-byte dump files this check.")

                if crash_found:
                    logger.error("Crash dump found. Stopping test.")
                    crash_handle(
                        self.cfg_mgr.is_64bit, 
                        current_log_dir, 
                        self.config.custom_dump_path
                    )
                    break

            except Exception:
                logger.exception("An error occurred:")
                logger.info(f"Retrying in {STD_SEC} seconds")
                if smart_sleep(STD_SEC, self.stop_event): 
                    break

        logger.info(f"--- Finished {count} iterations. ---")
        logger.info(f"Total 0-byte dumps deleted: {self.total_zero_dumps}")


if __name__ == "__main__":
    runner = StressTest()
    try:
        logger.info(f"Logging initialized: {current_log_dir}")
        runner.setup()
        runner.run()
    finally:
        runner.tear_down()
        sys.exit(0)