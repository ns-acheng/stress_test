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
        self.max_mem_usage = 85
        self.max_tabs_open = 20
        self.custom_dump_path = ""
        self.long_sleep_interval = 0
        self.long_sleep_time_min = 300
        self.long_sleep_time_max = 300
        
        self.traffic_dns_enabled = False
        self.traffic_udp_enabled = False
        self.traffic_concurrent_conns = 0
        self.traffic_udp_target = "127.0.0.1"
        self.traffic_ab_url = "http://127.0.0.1/"
        
        self.traffic_dns_count = 500
        self.traffic_udp_duration = 10

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
            self.max_mem_usage = config.get(
                'max_mem_usage', self.max_mem_usage
            )
            self.max_tabs_open = config.get(
                'max_tabs_open', self.max_tabs_open
            )
            self.custom_dump_path = config.get(
                'custom_dump_path', self.custom_dump_path
            )
            self.long_sleep_interval = config.get(
                'long_sleep_interval', self.long_sleep_interval
            )
            self.long_sleep_time_min = config.get(
                'long_sleep_time_min', self.long_sleep_time_min
            )
            self.long_sleep_time_max = config.get(
                'long_sleep_time_max', self.long_sleep_time_max
            )
            
            tg = config.get('traffic_gen', {})
            self.traffic_dns_enabled = bool(tg.get('dns_flood_enabled', 0))
            self.traffic_udp_enabled = bool(tg.get('udp_flood_enabled', 0))
            self.traffic_concurrent_conns = tg.get('concurrent_connections', 0)
            self.traffic_udp_target = tg.get('target_udp_ip', "127.0.0.1")
            self.traffic_ab_url = tg.get('target_ab_url', "http://127.0.0.1/")
            
            self.traffic_dns_count = tg.get('dns_query_count', 500)
            self.traffic_udp_duration = tg.get('udp_duration_seconds', 10)

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

        if not (50 <= self.max_mem_usage <= 99):
            logger.warning(
                f"Invalid 'max_mem_usage' {self.max_mem_usage}. "
                "Must be 50 ~ 99. Reset to 85."
            )
            self.max_mem_usage = 85

        if not (1 <= self.max_tabs_open <= 300):
            logger.warning(
                f"Invalid 'max_tabs_open' {self.max_tabs_open}. "
                "Must be 1 ~ 300. Reset to 20."
            )
            self.max_tabs_open = 20

        if self.long_sleep_time_max > 7200:
            logger.warning("long_sleep_time_max > 7200, capping at 7200.")
            self.long_sleep_time_max = 7200
            
        if self.long_sleep_time_min < 300:
            logger.warning("long_sleep_time_min < 300, capping at 300.")
            self.long_sleep_time_min = 300

        if self.long_sleep_time_max < self.long_sleep_time_min:
            logger.warning("long_sleep_time_max < min, adjusting to min.")
            self.long_sleep_time_max = self.long_sleep_time_min