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
        self.gateway_hosts = []
        self.failclose_active = False

    def load_nsexception(self):
        self.exception_names = []
        if not os.path.exists(self.exception_path):
            logger.warning(f"nsexception.json not found at {self.exception_path}")
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

            host = host.lower()

            for pattern in self.exception_names:
                pattern = pattern.lower()

                if fnmatch.fnmatch(host, pattern):
                    return True

                if pattern.startswith("*.") and host == pattern[2:]:
                    return True

                if '*' not in pattern and host.endswith('.' + pattern):
                    return True

            return False
        except Exception:
            return False

    def get_tenant_hostname(self) -> str:
        try:
            if not os.path.exists(self.target_nsconfig):
                return ""

            with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                data = json.load(f)

            nsgw = data.get("nsgw", {})
            host = nsgw.get("host") 

            if not host:
                return ""

            parts = host.split('.')
            if parts and parts[0].startswith("gateway-"):
                parts[0] = parts[0].replace("gateway-", "")
                return ".".join(parts)

            return ""

        except Exception as e:
            logger.error(f"Error reading tenant hostname from nsconfig: {e}")
            return ""

    def setup_environment(self) -> bool:
        check_path = r"C:\Program Files\Netskope\STAgent\stAgentSvc.exe"
        if os.path.exists(check_path):
            self.is_64bit = True
            logger.info(f"Detected 64-bit Agent: {check_path}")
        else:
            self.is_64bit = False
            logger.info("64-bit Agent path not found, assuming 32-bit.")

        if not os.path.exists(self.target_nsconfig):
            logger.error(f"ABORT: nsconfig.json not found at {self.target_nsconfig}. Client not installed.")
            return False

        try:
            with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            nsgw = data.get("nsgw", {})
            h1 = nsgw.get("host")
            h2 = nsgw.get("backupHost")

            if h1: self.gateway_hosts.append(h1)
            if h2: self.gateway_hosts.append(h2)

            logger.info(f"Loaded Gateway Hosts for FailClose simulation: {self.gateway_hosts}")

        except Exception as e:
            logger.error(f"Failed to load gateway hosts from nsconfig: {e}")
            # We don't necessarily abort here if file exists but read fails, 
            # though user only specified "if cannot find".

        if os.path.exists(self.hosts_path):
            try:
                shutil.copy(self.hosts_path, self.hosts_bk)
                logger.info(f"Backed up hosts file to {self.hosts_bk}")
            except Exception as e:
                logger.error(f"Failed to backup hosts file: {e}")
        
        return True

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
        logger.info("Executing FailClose simulation (Hosts manipulation + Config update)...")
        try:
            if self.failclose_active:
                # Restore Hosts
                if os.path.exists(self.hosts_bk):
                    try:
                        shutil.copy(self.hosts_bk, self.hosts_path)
                        logger.info("Restored hosts file (Simulating Network Recovery).")
                    except Exception as e:
                        logger.error(f"Failed to restore hosts file: {e}")
                else:
                    logger.error("Hosts backup not found, cannot restore.")

                # Revert FailClose config to false
                if os.path.exists(self.target_nsconfig):
                     try:
                         with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                             ns_data = json.load(f)
                         
                         ns_data.setdefault("failClose", {})["fail_close"] = "false"
                         
                         with open(self.target_nsconfig, 'w', encoding='utf-8') as f:
                             json.dump(ns_data, f, indent=4)
                         logger.info("Updated nsconfig.json: fail_close = false")
                     except Exception as e:
                         logger.error(f"Failed to update nsconfig.json: {e}")

                self.failclose_active = False
                self.is_false_close = False
            else:
                if not self.gateway_hosts:
                    logger.warning("No gateway hosts loaded. Cannot simulate FailClose.")
                    return

                if not os.path.exists(self.hosts_bk) and os.path.exists(self.hosts_path):
                    shutil.copy(self.hosts_path, self.hosts_bk)
                
                if not os.path.exists(self.backup_path) and os.path.exists(self.target_nsconfig):
                    shutil.copy(self.target_nsconfig, self.backup_path)

                # Deploy devconfig for FailClose
                if os.path.exists(self.source_devconfig):
                    shutil.copy(self.source_devconfig, self.target_devconfig)
                    logger.info(f"Copied devconfig to {self.target_devconfig}")
                    self.is_local_cfg = True
                else:
                    logger.warning(
                        f"Source {self.source_devconfig} not found. "
                        "FailClose might not work as expected."
                    )

                # Set FailClose config to true
                if os.path.exists(self.target_nsconfig):
                     try:
                         with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                             ns_data = json.load(f)
                         
                         ns_data.setdefault("failClose", {})["fail_close"] = "true"
                         
                         with open(self.target_nsconfig, 'w', encoding='utf-8') as f:
                             json.dump(ns_data, f, indent=4)
                         logger.info("Updated nsconfig.json: fail_close = true")
                     except Exception as e:
                         logger.error(f"Failed to update nsconfig.json: {e}")

                try:
                    with open(self.hosts_path, 'a', encoding='utf-8') as f:
                        f.write("\n# Stress Test FailClose Simulation\n")
                        for h in self.gateway_hosts:
                            f.write(f"10.1.1.1 {h}\n")
                        f.write("# End Stress Test \n")
                    
                    logger.info(
                        f"Blocked gateways {self.gateway_hosts} in hosts file "
                        "(Simulating Network Failure)."
                    )
                    self.failclose_active = True
                    self.is_false_close = True
                except Exception as e:
                    logger.error(f"Failed to modify hosts file: {e}")
                    
        except Exception as e:
            logger.error(f"Error during FailClose simulation: {e}")
