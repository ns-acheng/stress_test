import sys
import os
import random
import threading
from util_service import (
    start_service, stop_service, get_service_status, handle_non_stop
)
from util_log import LogSetup
from util_time import smart_sleep
from util_subprocess import (
    run_powershell, nsdiag_update_config, enable_wake_timers,
    nsdiag_enable_client
)
from util_resources import (
    log_resource_usage, enable_privilege
)
from util_input import start_input_monitor
from util_crash import check_crash_dumps, crash_handle
from util_config import AgentConfigManager
from util_tool_config import ToolConfig
from util_power import enter_s0_and_wake
import util_traffic
import util_client
import util_validate
import util_webui
from urllib.parse import urlparse
import re

TINY_SEC = 5
SHORT_SEC = 15
STD_SEC = 30
LONG_SEC = 60
BATCH_SIZE = 50

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
        self.url_cursor = 0
        self.manage_nic_script = os.path.join(self.tool_dir, "manage_nic.ps1")
        self.total_zero_dumps = 0
        self.client_thread = None
        self.validation_enabled = False
        self.client_enabled_event = threading.Event()
        self.client_enabled_event.set()

    def setup(self):
        for priv in ["SeDebugPrivilege", "SeSystemtimePrivilege", "SeWakeAlarmPrivilege"]:
            err = enable_privilege(priv)
            if err != 0:
                logger.warning(f"Failed to enable {priv}. Err: {err}")

        self.config.load()

        util_webui.perform_onprem_setup(self.config.config_data)

        self.load_urls()

        st_cfg = util_validate.get_steering_config()
        if not st_cfg:
            logger.warning("Steering config empty/not found. Validation disabled.")

        mode = st_cfg.get("firewall_traffic_mode")
        if not mode:
            mode = st_cfg.get("traffic_mode")

        if mode == "all" or mode == "web":
            self.validation_enabled = True
            logger.info(f"Validation Enabled. Mode: {mode}")
            util_validate.get_validator().update_pos_with_time_buffer(10)
        else:
            logger.info(f"Validation Disabled. Mode: '{mode}' (Requires 'all' or 'web')")

        if self.config.aoac_sleep_enabled:
            enable_wake_timers()

        self.cfg_mgr.setup_environment()
        self.cfg_mgr.restore_config(remove_only=True)

        logger.info("Setup: Ensuring Client is Enabled...")
        nsdiag_enable_client(True, self.cfg_mgr.is_64bit)

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
            with open(self.url_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            self.urls = [line.strip().rstrip('/') for line in lines if line.strip()]
            random.shuffle(self.urls)
            logger.info(f"Loaded {len(self.urls)} URLs from {self.url_file}")
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")

    def start_client_thread(self):
        if self.config.client_disabling_enabled:
            self.client_thread = threading.Thread(
                target=util_client.client_toggler_loop,
                args=(
                    self.stop_event,
                    self.service_name,
                    self.cfg_mgr.is_64bit,
                    self.config.client_enable_min,
                    self.config.client_enable_max,
                    self.config.client_disable_ratio,
                    self.client_enabled_event
                ),
                daemon=True
            )
            self.client_thread.start()

    def exec_failclose_check(self):
        if not os.path.exists(self.manage_nic_script):
            logger.error(f"NIC Manager not found: {self.manage_nic_script}")
            return
        logger.info("Simulating FailClose by Disabling NICs...")
        run_powershell(self.manage_nic_script, ["-Action", "Disable"])
        if smart_sleep(SHORT_SEC, self.stop_event):
            return
        test_urls = random.sample(self.urls, min(len(self.urls), 10))
        logger.info(f"Checking {len(test_urls)} URLs for reachability...")
        for url in test_urls:
            if self.stop_event.is_set(): break
            if util_traffic.check_url_alive(url):
                status = "ALIVE"
            else:
                status = "DEAD (Blocked)"
            logger.info(f"URL: {url} -> {status}")
            if smart_sleep(1, self.stop_event):
                break
        logger.info("FailClose check done. Re-Enabling NICs...")
        run_powershell(self.manage_nic_script, ["-Action", "Enable"])
        smart_sleep(SHORT_SEC, self.stop_event)

    def header_msg(self):
        logger.info(f"--------- Start. Total iter: {self.config.loop_times} ---------")
        logger.info(f"Stop svc int: {self.config.stop_svc_interval}")
        logger.info(f"Switch FailClose int: {self.config.failclose_interval}")
        logger.info(f"Stop/Start drv int: {self.config.stop_drv_interval}")
        logger.info(f"Client Disabling: {self.config.client_disabling_enabled}")
        logger.info(f"Browser Tabs Enabled: {self.config.enable_browser_tabs_open}")
        if self.config.enable_browser_tabs_open:
            logger.info(f"Max Mem: {self.config.browser_max_memory}%")
            logger.info(f"Max Tabs: {self.config.browser_max_tabs}")
        if self.config.aoac_sleep_enabled:
            logger.info(f"AOAC Sleep Int: {self.config.aoac_sleep_interval}")
            logger.info(f"AOAC Sleep Dur: {self.config.aoac_sleep_duration}s")
        if self.config.long_idle_interval > 0:
            logger.info(f"Long Idle Int: {self.config.long_idle_interval}")
            logger.info(
                f"Long Idle: {self.config.long_idle_time_min} - "
                f"{self.config.long_idle_time_max}s"
            )
        else:
            logger.info("Long Idle is 0. Random sleep 30-120s enabled.")
        if self.config.custom_dump_path:
            logger.info(f"Custom Dump Path: {self.config.custom_dump_path}")
        logger.info(f"Log Folder: {current_log_dir}")
        logger.info("--> Press ESC or Ctrl+C to stop. <--")
        logger.info("=" * 50)

    def exec_start_service(self):
        status = get_service_status(self.service_name)
        if status == "NOT_FOUND":
            logger.error(f"Service {self.service_name} NOT FOUND.")
            self.stop_event.set()
            return
        logger.info(f"Current status: {status}")
        if status != "RUNNING":
            start_service(self.service_name)
            logger.info(f"Waiting for {STD_SEC} seconds")
            if smart_sleep(STD_SEC, self.stop_event):
                return

            if self.config.client_disabling_enabled:
                logger.info("Service Started. Ensuring Client Enabled.")
                nsdiag_enable_client(True, self.cfg_mgr.is_64bit)

        log_resource_usage("stAgentSvc.exe", current_log_dir)

    def exec_stop_service(self):
        status = get_service_status(self.service_name)
        if status == "NOT_FOUND":
            logger.error(f"Service {self.service_name} NOT FOUND.")
            self.stop_event.set()
            return
        logger.info(f"Current status: {status}")
        if status == "RUNNING":
            log_resource_usage("stAgentSvc.exe", current_log_dir)
            stopped = stop_service(self.service_name)
            if not stopped:
                logger.error(f"{self.service_name} failed to stop.")
                handle_non_stop(
                    self.service_name,
                    self.cfg_mgr.is_64bit,
                    current_log_dir
                )
                self.stop_event.set()
                return
            self.cur_svc_status = get_service_status(self.service_name)
            logger.info(f"Current status: {self.cur_svc_status}")
            if smart_sleep(TINY_SEC, self.stop_event):
                return

    def exec_restart_driver(self):
        if get_service_status(self.drv_name) == "NOT_FOUND":
            logger.error(f"Driver {self.drv_name} NOT FOUND.")
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

    def exec_browser_tabs(self, urls):
        if not self.config.enable_browser_tabs_open:
            return []
        return util_traffic.open_browser_tabs(
            urls, self.tool_dir, self.config.browser_max_tabs,
            self.config.browser_max_memory, self.stop_event, current_log_dir,
            STD_SEC
        )

    def exec_curl_requests(self):
        util_traffic.curl_requests(self.urls, self.stop_event)

    def exec_validation_checks(self, process_map):
        if not self.validation_enabled:
            logger.info("Validation skipped (disabled by firewall_traffic_mode).")
            return True

        self.cfg_mgr.load_nsexception()

        if self.config.client_disabling_enabled and not self.client_enabled_event.is_set():
             logger.info("Validation skipped (Client is disabled).")
             return True

        return util_validate.validate_traffic_flow(
            process_map, self.stop_event, self.cfg_mgr.url_in_nsexception
        )

    def get_next_batch(self, batch_size):
        if not self.urls:
            return []

        if len(self.urls) <= batch_size:
            batch = self.urls[:]

            random.shuffle(self.urls)
            return batch

        end_idx = self.url_cursor + batch_size
        if end_idx <= len(self.urls):
            batch = self.urls[self.url_cursor : end_idx]
            self.url_cursor = end_idx
            if self.url_cursor == len(self.urls):
                 self.url_cursor = 0
                 random.shuffle(self.urls)
                 logger.info("All URLs used. Re-shuffling list.")
            return batch
        else:

            batch = self.urls[self.url_cursor :]

            random.shuffle(self.urls)
            logger.info("All URLs used. Re-shuffling list.")

            self.url_cursor = 0
            needed = batch_size - len(batch)
            if needed > 0:
                batch.extend(self.urls[0:needed])
                self.url_cursor = needed
            return batch
            needed = batch_size - len(batch)
            if needed > 0:
                batch.extend(self.urls[0:needed])
                self.url_cursor = needed
            return batch

    def run(self):
        start_input_monitor(self.stop_event)
        self.header_msg()
        self.start_client_thread()

        count = 0
        for count in range(1, self.config.loop_times + 1):
            if self.stop_event.is_set(): break
            try:
                pct = count / self.config.loop_times * 100
                msg = f" Iter {count}/{self.config.loop_times} ({pct:.1f}%) "
                logger.info(msg.center(60, "="))

                self.exec_start_service()
                if self.stop_event.is_set(): break

                if not self.cfg_mgr.is_local_cfg:
                    nsdiag_update_config(self.cfg_mgr.is_64bit)
                else:
                    logger.info("Local config active, skip nsdiag update")

                if self.stop_event.is_set(): break

                needed_size = 50
                if self.config.curl_flood_enabled:
                    needed_size += self.config.curl_flood_count
                if self.config.enable_browser_tabs_open:
                    needed_size += self.config.browser_max_tabs

                batch_size = max(50, needed_size)

                current_iter_urls = self.get_next_batch(batch_size)

                if self.config.dns_enabled:
                    dns_domains = []
                    for u in current_iter_urls:
                        try:
                            parsed = urlparse(u)
                            if parsed.netloc:
                                dns_domains.append(parsed.netloc)
                            else:
                                dns_domains.append(u.split('/')[0])
                        except Exception:
                            pass

                    util_traffic.generate_dns_flood(
                        dns_domains,
                        self.config.dns_count,
                        self.config.dns_duration,
                        self.config.dns_concurrent,
                        self.stop_event
                    )

                if self.config.udp_enabled:
                    current_target = self.config.udp_target_ip
                    use_ipv6 = False
                    if self.config.udp_target_ipv6:
                        if count % 2 == 0:
                            current_target = self.config.udp_target_ipv6
                            use_ipv6 = True
                        else:
                            current_target = self.config.udp_target_ip
                    util_traffic.generate_udp_flood(
                        current_target,
                        self.config.udp_target_port,
                        self.config.udp_count,
                        float(self.config.udp_duration),
                        self.config.udp_concurrent,
                        self.stop_event,
                        use_ipv6
                    )

                if (
                    (self.config.ab_total_conn > 0 or self.config.ab_duration > 0) and
                    self.config.ab_concurrent > 0 and
                    self.config.ab_target_urls
                ):
                    idx = count % len(self.config.ab_target_urls)
                    current_ab_url = self.config.ab_target_urls[idx]

                    if util_traffic.check_url_alive(current_ab_url):
                        util_traffic.run_high_concurrency_test(
                            current_ab_url, self.config.ab_total_conn,
                            self.config.ab_concurrent, self.tool_dir,
                            self.stop_event,
                            self.config.ab_duration
                        )
                    else:
                        logger.warning(f"AB Test skipped. URL not alive: {current_ab_url}")

                curl_flood_urls = []
                if self.config.curl_flood_enabled:

                    browser_count = 0
                    if self.config.enable_browser_tabs_open:
                        browser_count = self.config.browser_max_tabs

                    curl_targets = []
                    if len(current_iter_urls) >= (self.config.curl_flood_count + browser_count):

                         start_idx = browser_count
                         end_idx = start_idx + self.config.curl_flood_count
                         curl_targets = current_iter_urls[start_idx:end_idx]
                    else:

                         curl_targets = current_iter_urls[:]

                    curl_flood_urls = util_traffic.generate_curl_flood(
                        curl_targets,
                        self.config.curl_flood_count,
                        self.config.curl_flood_duration,
                        self.config.curl_flood_concurrent,
                        self.stop_event
                    )

                if self.config.ftp_enabled:
                    util_traffic.generate_ftp_traffic(
                        self.config.ftp_target_ip,
                        self.config.ftp_target_port,
                        self.config.ftp_user,
                        self.config.ftp_password,
                        self.config.ftp_file_size_mb,
                        self.config.ftp_count,
                        self.config.ftp_duration,
                        self.config.ftp_concurrent,
                        self.stop_event
                    )

                if self.config.ftps_enabled:
                    util_traffic.generate_ftps_traffic(
                        self.config.ftps_target_ip,
                        self.config.ftps_target_port,
                        self.config.ftps_user,
                        self.config.ftps_password,
                        self.config.ftps_file_size_mb,
                        self.config.ftps_count,
                        self.config.ftps_duration,
                        self.config.ftps_concurrent,
                        self.stop_event
                    )

                if self.config.sftp_enabled:
                    util_traffic.generate_sftp_traffic(
                        self.config.sftp_target_ip,
                        self.config.sftp_target_port,
                        self.config.sftp_user,
                        self.config.sftp_password,
                        self.config.sftp_file_size_mb,
                        self.config.sftp_count,
                        self.config.sftp_duration,
                        self.config.sftp_concurrent,
                        self.stop_event
                    )

                if self.stop_event.is_set(): break

                if self.cfg_mgr.is_false_close:
                    self.exec_failclose_check()
                else:

                    browser_targets = []
                    if self.config.enable_browser_tabs_open:
                        needed = self.config.browser_max_tabs
                        if len(current_iter_urls) >= needed:
                            browser_targets = current_iter_urls[:needed]
                        else:
                            browser_targets = current_iter_urls[:]

                    browser_urls = self.exec_browser_tabs(browser_targets)
                    if smart_sleep(2, self.stop_event): break

                    logger.info("Waiting for logs to be flushed...")
                    if smart_sleep(10, self.stop_event): break

                    validation_map = {}
                    if browser_urls and self.config.browser_log_validation:
                        validation_map["msedge.exe"] = browser_urls

                    if curl_flood_urls and self.config.curl_flood_log_validation:
                        ratio = self.config.curl_flood_log_validation_ratio
                        total = len(curl_flood_urls)
                        sample_size = int(total * (ratio / 100.0))
                        if sample_size < 1 and total > 0:
                            sample_size = 1
                        if sample_size > total:
                            sample_size = total

                        logger.info(f"Sampling {sample_size} URLs ({ratio}%) from {total} for validation.")
                        validation_map["curl.exe"] = random.sample(curl_flood_urls, sample_size)

                    if not self.exec_validation_checks(validation_map):
                        logger.error("Validation failed! Stopping stress test.")
                        break

                if self.stop_event.is_set(): break

                if self.config.stop_svc_interval > 0:
                    if count % self.config.stop_svc_interval == 0:
                        self.exec_stop_service()
                        if self.stop_event.is_set(): break

                        if self.config.stop_drv_interval > 0:
                            if count % self.config.stop_drv_interval == 0:
                                self.exec_restart_driver()
                                if self.stop_event.is_set(): break

                if self.config.failclose_enabled and self.config.failclose_interval > 0:
                    if count % self.config.failclose_interval == 0:
                        self.cfg_mgr.toggle_failclose()
                        if self.stop_event.is_set(): break

                if self.config.long_idle_interval == 0:
                    sleep_dur = random.randint(30, 120)
                    logger.info(f"Random Sleep (idle=0). {sleep_dur}s...")
                    if smart_sleep(sleep_dur, self.stop_event): break

                if self.config.aoac_sleep_enabled and self.config.aoac_sleep_interval > 0:
                    if count % self.config.aoac_sleep_interval == 0:
                        logger.info(
                            f"AOAC Sleep. {self.config.aoac_sleep_duration}s"
                        )
                        enter_s0_and_wake(self.config.aoac_sleep_duration)
                        if self.stop_event.is_set(): break

                if self.config.long_idle_interval > 0:
                    if count % self.config.long_idle_interval == 0:
                        sleep_dur = random.randint(
                            self.config.long_idle_time_min,
                            self.config.long_idle_time_max
                        )
                        logger.info(f"Long Idle triggered. {sleep_dur}s...")
                        if smart_sleep(sleep_dur, self.stop_event): break

                ps_script = os.path.join(self.tool_dir, "close_browsers.ps1")
                run_powershell(ps_script)
                if smart_sleep(SHORT_SEC, self.stop_event): break

                crash_found, zero_count = check_crash_dumps(
                    self.config.custom_dump_path
                )
                self.total_zero_dumps += zero_count
                if zero_count > 0:
                    logger.info(f"Cleaned {zero_count} 0-byte dump files.")
                if crash_found:
                    logger.error("Crash dump found. Stopping test.")
                    crash_handle(
                        self.cfg_mgr.is_64bit, current_log_dir,
                        self.config.custom_dump_path
                    )
                    break
            except Exception:
                logger.exception("An error occurred:")
                logger.info(f"Retrying in {STD_SEC} seconds")
                if smart_sleep(STD_SEC, self.stop_event): break

        logger.info(f"--------- Finished {count} iterations. ---------")
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
