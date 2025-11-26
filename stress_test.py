import sys
import json
import os
import shutil
import random
from util_service import start_service, stop_service, get_service_status
from util_log import setup_logging
from util_time import sleep_ex
from util_subprocess import run_batch, run_powershell

TINY_SEC = 5
SHORT_SEC = 15
STD_SEC = 30
LONG_SEC = 60

try:
    logger, log_file = setup_logging()
except Exception as e:
    print(f"Critical error during logging setup: {e}", file=sys.stderr)
    sys.exit(1)

class StressTest:
    def __init__(self):
        self.service_name = "stagentsvc"
        self.drv_name = "stadrv"
        self.config_file = "config.json"
        self.url_file = r"data\url.txt"
        self.stagent_root = r"C:\ProgramData\netskope\stagent"
        
        self.loop_times = 1000
        self.stop_svc_interval = 1
        self.stop_drv_interval = 0
        self.failclose_interval = 20
        self.urls = []

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {self.config_file}")
            
            self.loop_times = config.get('loop_times', self.loop_times)
            self.stop_svc_interval = config.get('stop_svc_interval', self.stop_svc_interval)
            self.stop_drv_interval = config.get('stop_drv_interval', self.stop_drv_interval)
            self.failclose_interval = config.get('failclose_interval', self.failclose_interval)

        except Exception as e:
            logger.error(f"Error loading config: {e}. Exiting.")
            sys.exit(1)

        if not isinstance(self.loop_times, int) or self.loop_times <= 0:
            logger.error(f"invalid 'loop_times'. Exiting.")
            sys.exit(1)
            
        if not isinstance(self.stop_svc_interval, int) or self.stop_svc_interval < 0:
            logger.error(f"invalid 'stop_svc_interval'. Exiting.")
            sys.exit(1)
            
        if not isinstance(self.failclose_interval, int) or self.failclose_interval < 0:
            logger.error(f"invalid 'failclose_interval'. Exiting.")
            sys.exit(1)

        if not isinstance(self.stop_drv_interval, int) or self.stop_drv_interval < 0:
            logger.error(f"invalid 'stop_drv_interval'. Exiting.")
            sys.exit(1)

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

    def restore_config(self):
        logger.info("--- Restoring Original Configuration ---")
        try:
            backup_path = os.path.join(".", "data", "nsconfig-bk.json")
            target_nsconfig = os.path.join(self.stagent_root, "nsconfig.json")
            target_devconfig = os.path.join(self.stagent_root, "devconfig.json")

            if os.path.exists(backup_path):
                shutil.move(backup_path, target_nsconfig)
                logger.info(f"Restored {backup_path} back to {target_nsconfig}")
            else:
                logger.warning(f"Backup file {backup_path} not found. Cannot restore.")

            if os.path.exists(target_devconfig):
                os.remove(target_devconfig)
                logger.info(f"Removed {target_devconfig}")
            else:
                logger.info(f"{target_devconfig} not found, skipping removal.")

        except Exception as e:
            logger.error(f"Error during config restoration: {e}")

    def exec_failclose_change(self):
        logger.info("Executing FailClose configuration change...")
        try:
            nsconfig_path = os.path.join(self.stagent_root, "nsconfig.json")
            backup_path = os.path.join(".", "data", "nsconfig-bk.json")
            devconfig_src = os.path.join(".", "data", "devconfig.json")

            if not os.path.exists(backup_path):
                if os.path.exists(nsconfig_path):
                    shutil.copy(nsconfig_path, backup_path)
                    logger.info(f"Backed up nsconfig.json to {backup_path}")
                else:
                    logger.warning(f"Original file {nsconfig_path} not found.")

            if os.path.exists(devconfig_src):
                shutil.copy(devconfig_src, self.stagent_root)
                logger.info(f"Copied {devconfig_src} to {self.stagent_root}")
            else:
                logger.warning(f"Source file {devconfig_src} not found.")

            if os.path.exists(nsconfig_path):
                with open(nsconfig_path, 'r') as f:
                    ns_data = json.load(f)
                
                fc_section = ns_data.get("failClose", {})
                current_val = fc_section.get("fail_close", "false")

                if current_val == "true":
                    new_config = {
                        "fail_close": "false",
                        "exclude_npa": "false",
                        "notification": "false",
                        "captive_portal_timeout": "0"
                    }
                    logger.info("Switching FailClose to FALSE")
                else:
                    new_config = {
                        "fail_close": "true",
                        "exclude_npa": "false",
                        "notification": "false",
                        "captive_portal_timeout": "0"
                    }
                    logger.info("Switching FailClose to TRUE")
                
                ns_data["failClose"] = new_config

                with open(nsconfig_path, 'w') as f:
                    json.dump(ns_data, f, indent=4)
                logger.info("nsconfig.json updated successfully.")
            else:
                logger.error(f"Target file {nsconfig_path} not found.")

        except Exception as e:
            logger.error(f"Error during FailClose config change: {e}")

    def header_msg(self):
        logger.info(f"--- Start Testing. Total iterations: {self.loop_times} ---")
        logger.info(f"Stop service every {self.stop_svc_interval} run(s) (0 = never)")
        logger.info(f"Switch FailClose every {self.failclose_interval} run(s) (0 = never)")
        logger.info(f"Stop/Start driver every {self.stop_drv_interval} run(s) (0 = never)")
        logger.info("=" * 50)

    def exec_start_service(self):
        current_status = get_service_status(self.service_name)
        logger.info(f"Current status: {current_status}")
        if current_status != "RUNNING":
            start_service(self.service_name)
            logger.info(f"Waiting for {STD_SEC} seconds")
            sleep_ex(STD_SEC)

    def exec_stop_service(self):
        current_status = get_service_status(self.service_name)
        logger.info(f"Current status: {current_status}")
        if current_status == "RUNNING":
            logger.info(f"To STOP '{self.service_name}'")
            stop_service(self.service_name)
            self.cur_svc_status = get_service_status(self.service_name)
            logger.info(f"Current status: {self.cur_svc_status}")
            sleep_ex(TINY_SEC)

    def exec_restart_driver(self):
        logger.info(f"To STOP and START driver 'stadrv'")
        stop_service(self.drv_name)
        current_status = get_service_status(self.service_name)
        logger.info(f"Current status: {current_status}")
        sleep_ex(SHORT_SEC)
        start_service(self.drv_name)
        sleep_ex(TINY_SEC)
    
    def exec_browser_tabs(self):
        if not self.urls:
            logger.warning("No URLs loaded to open.")
            return
        count = min(len(self.urls), 10)
        selected_urls = random.sample(self.urls, count)
        logger.info(f"Opening URLs: {selected_urls}")
        args = " ".join(selected_urls)
        cmd = f"data\\open_urls.bat {args}"
        
        run_batch(cmd)
        sleep_ex(LONG_SEC)

    def run(self):
        self.header_msg()
        self.load_urls()

        for loop_count in range(1, self.loop_times + 1):
            try:
                logger.info(f"==== Iteration {loop_count} / {self.loop_times} ====")

                self.exec_start_service()
                self.exec_browser_tabs()

                if self.failclose_interval > 0 and loop_count % self.failclose_interval == 0:
                    self.exec_failclose_change()

                if self.stop_svc_interval > 0 and loop_count % self.stop_svc_interval == 0:
                    self.exec_stop_service()
                    if self.stop_drv_interval > 0 and loop_count % self.stop_drv_interval == 0:
                        self.exec_restart_driver()

                sleep_ex(STD_SEC)
                run_powershell("close_msedge.ps1")

            except KeyboardInterrupt:
                logger.info("Loop stopped by user. Exiting.")
                self.restore_config()
                return
            except Exception:
                logger.exception("An error occurred:")
                logger.info(f"Retrying in {STD_SEC} seconds")
                sleep_ex(STD_SEC)

        self.restore_config()
        logger.info(f"--- Testing finished after {self.loop_times} iterations. ---")


if __name__ == "__main__":
    try:
        logger.info(f"Logging initialized. Log file: {log_file}")
        test_runner = StressTest()
        test_runner.load_config()
        test_runner.run()
    except KeyboardInterrupt:
        logger.info("Loop stopped by user. Exiting.")
        sys.exit(0)