import json
import sys
import logging
import os

logger = logging.getLogger()

class ToolConfig:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.loop_times = 1000
        self.stop_svc_interval = 1
        self.stop_drv_interval = 0
        self.failclose_interval = 20
        self.disable_client = 0
        self.max_mem_usage = 85
        self.max_tabs_open = 20
        self.custom_dump_path = ""
        self.long_idle_interval = 0
        self.long_idle_time_min = 300
        self.long_idle_time_max = 300
        self.system_sleep_interval = 0
        self.system_sleep_seconds = 60
        self.traffic_dns_enabled = False
        self.traffic_udp_enabled = False
        self.ab_total_conn = 10000
        self.ab_concurrent_conn = 0
        self.ab_urls = ["https://google.com"]
        self.udp_target_ip = "127.0.0.1"
        self.udp_target_ipv6 = ""
        self.udp_target_port = 8080
        self.traffic_dns_count = 500
        self.traffic_udp_duration = 10
        self.curl_flood_enabled = False
        self.curl_flood_count = 1000
        self.curl_flood_concurrency = 50

    def load(self):
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
            self.disable_client = config.get(
                'disable_client', self.disable_client
            )
            self.max_mem_usage = config.get(
                'max_mem_usage', self.max_mem_usage
            )
            self.max_tabs_open = config.get(
                'max_tabs_open', self.max_tabs_open
            )
            self.custom_dump_path = config.get(
                'custom_dump_path', self.custom_dump_path
            )
            self.long_idle_interval = config.get(
                'long_idle_interval', self.long_idle_interval
            )
            self.long_idle_time_min = config.get(
                'long_idle_time_min', self.long_idle_time_min
            )
            self.long_idle_time_max = config.get(
                'long_idle_time_max', self.long_idle_time_max
            )
            self.system_sleep_interval = config.get(
                'system_sleep_interval', self.system_sleep_interval
            )
            self.system_sleep_seconds = config.get(
                'system_sleep_seconds', self.system_sleep_seconds
            )
            
            tg = config.get('traffic_gen', {})
            self.traffic_dns_enabled = bool(tg.get('dns_flood_enabled', 0))
            self.traffic_udp_enabled = bool(tg.get('udp_flood_enabled', 0))
            self.ab_total_conn = tg.get('ab_total_conn', 10000)
            self.ab_concurrent_conn = tg.get('ab_concurrent_conn', 0)
            self.udp_target_ip = tg.get('udp_target_ip', "127.0.0.1")
            self.udp_target_ipv6 = tg.get('udp_target_ipv6', "")
            self.udp_target_port = tg.get('udp_target_port', 8080)
            self.ab_urls = tg.get('ab_urls', ["https://google.com"])
            if not isinstance(self.ab_urls, list):
                if self.ab_urls:
                    self.ab_urls = [self.ab_urls]
                else:
                    self.ab_urls = ["https://google.com"]
            self.traffic_dns_count = tg.get('dns_query_count', 500)
            self.traffic_udp_duration = tg.get('udp_duration_seconds', 10)
            self.curl_flood_enabled = bool(tg.get('curl_flood_enabled', 0))
            self.curl_flood_count = tg.get('curl_flood_count', 1000)
            self.curl_flood_concurrency = tg.get('curl_flood_concurrency', 50)

        except Exception as e:
            logger.error(f"Error loading config: {e}. Exiting.")
            sys.exit(1)

        self._validate()

    def _validate(self):
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
        if self.disable_client not in [0, 1]:
            logger.warning("invalid 'disable_client', reset to 0.")
            self.disable_client = 0
        if not (50 <= self.max_mem_usage <= 99):
            logger.warning("Invalid 'max_mem_usage'. Reset to 85.")
            self.max_mem_usage = 85
        if not (1 <= self.max_tabs_open <= 300):
            logger.warning("Invalid 'max_tabs_open'. Reset to 20.")
            self.max_tabs_open = 20
        if self.long_idle_time_max > 7200:
            logger.warning("long_idle_time_max > 7200, capping at 7200.")
            self.long_idle_time_max = 7200
        if self.long_idle_time_min < 300:
            logger.warning("long_idle_time_min < 300, capping at 300.")
            self.long_idle_time_min = 300
        if self.long_idle_time_max < self.long_idle_time_min:
            logger.warning("long_idle_time_max < min, adjusting to min.")
            self.long_idle_time_max = self.long_idle_time_min
        if self.system_sleep_interval < 0:
            logger.error("invalid 'system_sleep_interval'. Exiting.")
            sys.exit(1)
        if not (60 <= self.system_sleep_seconds <= 600):
             logger.warning("Invalid 'system_sleep_seconds'. Resetting to 60.")
             self.system_sleep_seconds = 60
        if self.ab_total_conn < 0:
             logger.warning("ab_total_conn < 0, disabling (0).")
             self.ab_total_conn = 0
        if self.curl_flood_count < 0:
            self.curl_flood_count = 0
        if self.curl_flood_concurrency < 1:
            self.curl_flood_concurrency = 1