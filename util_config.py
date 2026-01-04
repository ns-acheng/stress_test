import os
import shutil
import json
import logging
import fnmatch
from util_traffic import get_hostname_from_url

logger = logging.getLogger()

class AgentConfigManager:
    def __init__(self):
        self.stagent_root = r"C:\ProgramData\netskope\stagent"
        self.target_nsconfig = os.path.join(self.stagent_root, "nsconfig.json")
        self.target_devconfig = os.path.join(self.stagent_root, "devconfig.json")
        self.backup_path = os.path.join("data", "nsconfig-bk.json")
        self.source_devconfig = os.path.join("data", "devconfig.json")

        self.hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        self.hosts_bk = os.path.join("data", "hosts-bk")

        self.is_64bit = False
        self.is_local_cfg = False
        self.is_false_close = False

        self.exception_path = os.path.join(
            self.stagent_root, "data", "nsexception.json"
        )
        self.exception_names = []
        self.load_nsexception()

    def load_nsexception(self):
        self.exception_names = []
        if not os.path.exists(self.exception_path):
            return

        try:
            with open(self.exception_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict):
                if "names" in data and isinstance(data["names"], list):
                    self.exception_names.extend(data["names"])

            elif isinstance(data, list):
                for rule in data:
                    names = rule.get("names", [])
                    if isinstance(names, list):
                        self.exception_names.extend(names)

            logger.info(
                f"Loaded {len(self.exception_names)} exception patterns "
                f"from {self.exception_path}"
            )
        except Exception as e:
            logger.error(f"Failed to load nsexception.json: {e}")

    def url_in_nsexception(self, url: str) -> bool:
        try:
            host = get_hostname_from_url(url)
            if not host:
                return False

            for pattern in self.exception_names:
                if fnmatch.fnmatch(host, pattern):
                    return True
            return False
        except Exception:
            return False

    def setup_environment(self):
        check_path = r"C:\Program Files\Netskope\STAgent\stAgentSvc.exe"
        if os.path.exists(check_path):
            self.is_64bit = True
            logger.info(f"Detected 64-bit Agent: {check_path}")
        else:
            self.is_64bit = False
            logger.info("64-bit Agent path not found, assuming 32-bit.")

        if os.path.exists(self.hosts_path):
            try:
                shutil.copy(self.hosts_path, self.hosts_bk)
                logger.info(f"Backed up hosts file to {self.hosts_bk}")
            except Exception as e:
                logger.error(f"Failed to backup hosts file: {e}")

    def restore_config(self, remove_only=False):
        try:
            if os.path.exists(self.backup_path):
                if remove_only:
                    os.remove(self.backup_path)
                    logger.info(f"Removed backup {self.backup_path}")
                else:
                    shutil.move(self.backup_path, self.target_nsconfig)
                    logger.info(f"Restored {self.backup_path}")
            else:
                if not remove_only:
                    logger.warning(f"Backup {self.backup_path} not found.")

            if os.path.exists(self.target_devconfig):
                os.remove(self.target_devconfig)
                logger.info(f"Removed {self.target_devconfig}")

            if os.path.exists(self.hosts_bk):
                if remove_only:
                    os.remove(self.hosts_bk)
                else:
                    shutil.copy(self.hosts_bk, self.hosts_path)
                    logger.info(f"Restored hosts file from {self.hosts_bk}")

        except Exception as e:
            logger.error(f"Error during config restoration: {e}")
        self.is_local_cfg = False

    def toggle_failclose(self):
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
                logger.info(f"Copied devconfig to {self.target_devconfig}")
                self.is_local_cfg = True
            else:
                logger.warning(f"Source {self.source_devconfig} not found.")

            if os.path.exists(self.target_nsconfig):
                with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
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
                    self.is_false_close = False
                else:
                    new_cfg = {
                        "fail_close": "true",
                        "exclude_npa": "false",
                        "notification": "false",
                        "captive_portal_timeout": "0"
                    }
                    logger.info("Switching FailClose to TRUE")
                    self.is_false_close = True

                ns_data["failClose"] = new_cfg

                with open(self.target_nsconfig, 'w', encoding='utf-8') as f:
                    json.dump(ns_data, f, indent=4)
                logger.info(f"{self.target_nsconfig} updated successfully.")
            else:
                logger.error(f"Target file {self.target_nsconfig} not found.")
        except Exception as e:
            logger.error(f"Error during FailClose config change: {e}")
