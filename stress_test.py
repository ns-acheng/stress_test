import sys
import json
import os
import shutil
import random
import glob
import threading
import msvcrt
import time
from util_service import start_service, stop_service, get_service_status
from util_log import LogSetup
from util_time import sleep_ex
from util_subprocess import (
    run_batch, 
    run_powershell, 
    nsdiag_update_config
)
from util_resources import (
    get_system_memory_usage, 
    log_resource_usage, 
    enable_debug_privilege
)

TINY_SEC = 5
SHORT_SEC = 15
STD_SEC = 30
LONG_SEC = 60

if not os.path.exists("log"):
    os.makedirs("log")

try:
    log_helper = LogSetup()
    logger = log_helper.setup_logging()
    current_timestamp = log_helper.get_timestamp()
except Exception as e:
    print(f"Critical error during logging setup: {e}", file=sys.stderr)
    sys.exit(1)

class StressTest:
    def __init__(self):
        self.service_name = "stagentsvc"
        self.drv_name = "stadrv"
        self.config_file = r"data\config.json"
        self.url_file = r"data\url.txt"
        self.tool_dir = "tool"
        self.stagent_root = r"C:\ProgramData\netskope\stagent"
        self.is_64bit = False
        self.is_local_cfg = False

        self.loop_times = 1000
        self.stop_svc_interval = 1
        self.stop_drv_interval = 0
        self.failclose_interval = 20
        self.max_mem_usage = 85
        self.urls = []

        self.backup_path = os.path.join("data", "nsconfig-bk.json")
        self.source_devconfig = os.path.join("data", "devconfig.json")
        self.target_nsconfig = os.path.join(self.stagent_root, "nsconfig.json")
        self.target_devconfig = os.path.join(self.stagent_root, "devconfig.json")

    def setup(self):
        enable_debug_privilege()
        self.load_tool_config()
        self.load_urls()
        self.restore_client_config(remove_only=True)
        
        check_path = r"C:\Program Files\Netskope\STAgent\stAgentSvc.exe"
        if os.path.exists(check_path):
            self.is_64bit = True
            logger.info(f"Detected 64-bit Agent: {check_path}")
        else:
            self.is_64bit = False
            logger.info("64-bit Agent path not found, assuming 32-bit.")

    def tear_down(self):
        self.restore_client_config()

    def input_monitor(self):
        logger.info("Input monitor started. Press ESC to stop test.")
        while True:
            if msvcrt.kbhit():
                try:
                    key = msvcrt.getch()
                    if key == b'\x1b' or key == b'\x03':
                        logger.warning("Stop detected. Teardown initiated...")
                        self.tear_down()
                        logger.info("Tear Down complete. Exiting.")
                        os._exit(0)
                except Exception:
                    pass
            time.sleep(0.1)

    def load_tool_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {self.config_file}")
            
            self.loop_times = config.get('loop_times', self.loop_times)
            self.stop_svc_interval = config.get(
                'stop_svc_interval', self.stop_svc_interval
            )
            self.stop_drv_interval = config.get(
                'stop_drv_interval', self.stop_drv_interval
            )
            self.failclose_interval = config.get(
                'failclose_interval', self.failclose_interval
            )
            self.max_mem_usage = config.get(
                'max_mem_usage', self.max_mem_usage
            )

        except Exception as e:
            logger.error(f"Error loading config: {e}. Exiting.")
            sys.exit(1)

        if not isinstance(self.loop_times, int) or self.loop_times <= 0:
            logger.error(f"invalid 'loop_times'. Exiting.")
            sys.exit(1)
            
        if self.stop_svc_interval < 0:
            logger.error(f"invalid 'stop_svc_interval'. Exiting.")
            sys.exit(1)
            
        if self.failclose_interval < 0:
            logger.error(f"invalid 'failclose_interval'. Exiting.")
            sys.exit(1)

        if self.stop_drv_interval < 0:
            logger.error(f"invalid 'stop_drv_interval'. Exiting.")
            sys.exit(1)

        if not (50 <= self.max_mem_usage <= 99):
            logger.warning(
                f"Invalid 'max_mem_usage' {self.max_mem_usage}. "
                "Must be 50 ~ 99. Reset to 85."
            )
            self.max_mem_usage = 85

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

    def restore_client_config(self, remove_only=False):
        try:
            if os.path.exists(self.backup_path):
                if remove_only:
                    os.remove(self.backup_path)
                    logger.info(f"Removed backup {self.backup_path}")
                else:
                    shutil.move(self.backup_path, self.target_nsconfig)
                    logger.info(
                        f"Restored {self.backup_path} to {self.target_nsconfig}"
                    )
            else:
                if not remove_only:
                    logger.warning(
                        f"Backup {self.backup_path} not found. No restore."
                    )

            if os.path.exists(self.target_devconfig):
                os.remove(self.target_devconfig)
                logger.info(f"Removed {self.target_devconfig}")
        except Exception as e:
            logger.error(f"Error during config restoration: {e}")
        self.is_local_cfg = False

    def exec_failclose_change(self):
        logger.info("Executing FailClose configuration change...")
        try:
            if not os.path.exists(self.backup_path):
                if os.path.exists(self.target_nsconfig):
                    shutil.copy(self.target_nsconfig, self.backup_path)
                    logger.info(f"Backed up nsconfig to {self.backup_path}")
                else:
                    logger.warning(f"File {self.target_nsconfig} not found.")

            if os.path.exists(self.source_devconfig):
                shutil.copy(self.source_devconfig, self.target_devconfig)
                logger.info(
                    f"Copied {self.source_devconfig} to {self.target_devconfig}"
                )
                self.is_local_cfg = True
            else:
                logger.warning(f"Source {self.source_devconfig} not found.")

            if os.path.exists(self.target_nsconfig):
                with open(self.target_nsconfig, 'r') as f:
                    ns_data = json.load(f)
                
                fc_sec = ns_data.get("failClose", {})
                curr_val = fc_sec.get("fail_close", "false")

                if curr_val == "true":
                    new_cfg = {
                        "fail_close": "false",
                        "exclude_npa": "false",
                        "notification": "false",
                        "captive_portal_timeout": "0"
                    }
                    logger.info("Switching FailClose to FALSE")
                else:
                    new_cfg = {
                        "fail_close": "true",
                        "exclude_npa": "false",
                        "notification": "false",
                        "captive_portal_timeout": "0"
                    }
                    logger.info("Switching FailClose to TRUE")
                
                ns_data["failClose"] = new_cfg

                with open(self.target_nsconfig, 'w') as f:
                    json.dump(ns_data, f, indent=4)
                logger.info(f"{self.target_nsconfig} updated successfully.")
            else:
                logger.error(f"Target file {self.target_nsconfig} not found.")
        except Exception as e:
            logger.error(f"Error during FailClose config change: {e}")

    def header_msg(self):
        logger.info(f"--- Start. Total iterations: {self.loop_times} ---")
        logger.info(f"Stop service interval: {self.stop_svc_interval}")
        logger.info(f"Switch FailClose interval: {self.failclose_interval}")
        logger.info(f"Stop/Start driver interval: {self.stop_drv_interval}")
        logger.info(f"Max Memory Threshold: {self.max_mem_usage}%")
        logger.info("=" * 50)

    def exec_start_service(self):
        status = get_service_status(self.service_name)
        logger.info(f"Current status: {status}")
        if status != "RUNNING":
            start_service(self.service_name)
            logger.info(f"Waiting for {STD_SEC} seconds")
            sleep_ex(STD_SEC)
        log_resource_usage("stAgentSvc.exe", current_timestamp, log_dir="log")

    def exec_stop_service(self):
        status = get_service_status(self.service_name)
        logger.info(f"Current status: {status}")
        if status == "RUNNING":
            log_resource_usage("stAgentSvc.exe", current_timestamp, log_dir="log")
            stop_service(self.service_name)
            self.cur_svc_status = get_service_status(self.service_name)
            logger.info(f"Current status: {self.cur_svc_status}")
            sleep_ex(TINY_SEC)

    def exec_restart_driver(self):
        logger.info(f"To STOP and START driver 'stadrv'")
        stop_service(self.drv_name)
        status = get_service_status(self.service_name)
        logger.info(f"Current status: {status}")
        sleep_ex(SHORT_SEC)
        start_service(self.drv_name)
        sleep_ex(TINY_SEC)
    
    def exec_browser_tabs(self):
        if not self.urls:
            logger.warning("No URLs loaded to open.")
            return

        logger.info(
            f"Start tab opening loop. Target Memory: {self.max_mem_usage}%"
        )
        
        batch_limit = 20 
        batch_cnt = 0
        
        while batch_cnt < batch_limit:
            count = min(len(self.urls), 10)
            selected_urls = random.sample(self.urls, count)
            logger.info(
                f"Opening batch {batch_cnt + 1} ({len(selected_urls)} URLs)..."
            )
            
            args = " ".join(selected_urls)
            cmd = os.path.join(self.tool_dir, f"open_urls.bat {args}")
            run_batch(cmd)

            sleep_ex(STD_SEC)
            log_resource_usage("stAgentSvc.exe", current_timestamp, log_dir="log")

            mem_usage = get_system_memory_usage()
            mem_pct = mem_usage * 100.0   
            logger.info(
                f"System Memory: {mem_pct:.2f}% (Target: {self.max_mem_usage}%)"
            )

            if mem_pct >= self.max_mem_usage:
                logger.info(
                    f"Threshold reached ({mem_pct:.2f}% >= {self.max_mem_usage}%)."
                )
                break

            batch_cnt += 1

        if batch_cnt >= batch_limit:
            logger.warning(f"Reached maximum batch limit ({batch_limit})")

    def check_crash_dumps(self):
        dump_paths = [
            r"C:\dump\stAgentSvc.exe\*.dmp",
            r"C:\ProgramData\netskope\stagent\logs\*.dmp"
        ]
        found = False
        for path in dump_paths:
            files = glob.glob(path)
            if files:
                logger.error(f"CRASH DUMP DETECTED at: {path}")
                for f in files:
                    logger.error(f"File: {f}")
                found = True
        return found

    def run(self):
        th = threading.Thread(target=self.input_monitor, daemon=True)
        th.start()

        self.header_msg()

        for count in range(1, self.loop_times + 1):
            try:
                logger.info(f"==== Iteration {count} / {self.loop_times} ====")

                self.exec_start_service()
                
                if not self.is_local_cfg:
                    nsdiag_update_config(self.is_64bit)
                else:
                    logger.info("Local config active, skip nsdiag update")

                self.exec_browser_tabs()

                if self.failclose_interval > 0:
                    if count % self.failclose_interval == 0:
                        self.exec_failclose_change()

                if self.stop_svc_interval > 0:
                    if count % self.stop_svc_interval == 0:
                        self.exec_stop_service()
                        if self.stop_drv_interval > 0:
                            if count % self.stop_drv_interval == 0:
                                self.exec_restart_driver()

                sleep_ex(STD_SEC)
                ps_script = os.path.join(self.tool_dir, "close_msedge.ps1")
                run_powershell(ps_script)
                sleep_ex(SHORT_SEC)

                if self.check_crash_dumps():
                    logger.error("Crash dump found. Stopping test.")
                    break

            except KeyboardInterrupt:
                logger.info("Loop stopped by user. Exiting.")
                return
            except Exception:
                logger.exception("An error occurred:")
                logger.info(f"Retrying in {STD_SEC} seconds")
                sleep_ex(STD_SEC)

        logger.info(f"--- Finished {self.loop_times} iterations. ---")


if __name__ == "__main__":
    runner = StressTest()
    try:
        logger.info(f"Logging initialized: {current_timestamp}")
        runner.setup()
        runner.run()
    except KeyboardInterrupt:
        logger.info("Loop stopped by user. Exiting.")
    finally:
        runner.tear_down()
        sys.exit(0)