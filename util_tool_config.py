import json
import sys
import logging

logger = logging.getLogger()

class ToolConfig:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.loop_times = 1000
        self.stop_svc_interval = 1
        self.stop_drv_interval = 0
        self.failclose_enabled = True
        self.failclose_interval = 20
        self.client_disabling_enabled = False
        self.client_enable_min = 180
        self.client_enable_max = 600
        self.client_disable_ratio = 0.15
        self.custom_dump_path = ""
        self.long_idle_interval = 0
        self.long_idle_time_min = 300
        self.long_idle_time_max = 300
        self.aoac_sleep_enabled = False
        self.aoac_sleep_interval = 0
        self.aoac_sleep_duration = 60
        self.traffic_dns_enabled = False
        self.traffic_udp_enabled = False
        self.enable_browser_tabs_open = 1
        self.browser_max_memory = 85
        self.browser_max_tabs = 20
        self.ab_total_conn = 10000
        self.ab_concurrent_conn = 0
        self.ab_duration = 0
        self.ab_target_urls = ["https://google.com"]
        self.udp_target_ip = "127.0.0.1"
        self.udp_target_ipv6 = ""
        self.udp_target_port = 8080
        self.traffic_dns_count = 500
        self.traffic_dns_duration = 0
        self.traffic_dns_concurrent = 20
        self.traffic_udp_duration = 10
        self.traffic_udp_count = 0
        self.traffic_udp_concurrent = 1
        self.curl_flood_enabled = False
        self.curl_flood_count = 1000
        self.curl_flood_duration = 0
        self.curl_flood_concurrency = 50

    def load(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {self.config_file}")
            
            self.loop_times = config.get('loop_times', self.loop_times)
            self.stop_svc_interval = config.get(
                'stop_svc_interval', self.stop_svc_interval
            )
            self.stop_drv_interval = config.get(
                'stop_drv_interval', self.stop_drv_interval
            )
            
            cft = config.get('client_feature_toggling', {})
            
            cft_failclose = cft.get('failclose', {})
            self.failclose_enabled = bool(cft_failclose.get('enable', 1))
            self.failclose_interval = cft_failclose.get('interval', 20)

            cft_client = cft.get('client_disabling', {})
            self.client_disabling_enabled = bool(cft_client.get('enable', 0))
            self.client_enable_min = cft_client.get('enable_sec_min', 180)
            self.client_enable_max = cft_client.get('enable_sec_max', 600)
            self.client_disable_ratio = cft_client.get('disable_ratio', 0.15)

            cft_aoac = cft.get('aoac_sleep', {})
            self.aoac_sleep_enabled = bool(cft_aoac.get('enable', 0))
            self.aoac_sleep_interval = cft_aoac.get('interval', 0)
            self.aoac_sleep_duration = cft_aoac.get('duration_sec', 60)

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
            
            tg = config.get('traffic_gen', {})
            
            tg_browser = tg.get('browser', {})
            self.enable_browser_tabs_open = tg_browser.get('enable', 1)
            self.browser_max_memory = tg_browser.get('max_memory', 60)
            self.browser_max_tabs = tg_browser.get('max_tabs', 20)

            tg_dns = tg.get('dns', {})
            self.traffic_dns_enabled = bool(tg_dns.get('enable', 1))
            self.traffic_dns_count = tg_dns.get('count', 500)
            self.traffic_dns_duration = tg_dns.get('duration_sec', 0)
            self.traffic_dns_concurrent = tg_dns.get('concurrent_conn', 20)

            tg_udp = tg.get('udp', {})
            self.traffic_udp_enabled = bool(tg_udp.get('enable', 1))
            self.udp_target_ip = tg_udp.get('target_ip', "127.0.0.1")
            self.udp_target_ipv6 = tg_udp.get('target_ipv6', "")
            self.udp_target_port = tg_udp.get('target_port', 8080)
            self.traffic_udp_duration = tg_udp.get('duration_sec', 10)
            self.traffic_udp_count = tg_udp.get('count', 0)
            self.traffic_udp_concurrent = tg_udp.get('concurrent_conn', 1)

            tg_ab = tg.get('ab', {})
            ab_enabled = tg_ab.get('enable', 1)
            self.ab_total_conn = tg_ab.get('total_conn', 10000)
            self.ab_concurrent_conn = tg_ab.get('concurrent_conn', 0)
            self.ab_duration = tg_ab.get('duration_sec', 0)
            
            if not ab_enabled:
                self.ab_total_conn = 0
                self.ab_duration = 0
                
            self.ab_target_urls = tg_ab.get('target_urls', ["https://google.com"])
            if not isinstance(self.ab_target_urls, list):
                if self.ab_target_urls:
                    self.ab_target_urls = [self.ab_target_urls]
                else:
                    self.ab_target_urls = ["https://google.com"]

            tg_https = tg.get('https', {})
            self.curl_flood_enabled = bool(tg_https.get('enable', 1))
            self.curl_flood_count = tg_https.get('count', 1000)
            self.curl_flood_duration = tg_https.get('duration_sec', 0)
            self.curl_flood_concurrency = tg_https.get('concurrent_conn', 50)

        except Exception as e:
            logger.error(f"Error loading config: {e}. Exiting.")
            sys.exit(1)

        self._validate()

    def _validate_traffic_section(self, enabled, duration, count, name):
        if not enabled:
            return False
        if duration <= 0 and count <= 0:
            logger.warning(
                f"Both duration and count are 0 for {name}. Disabling."
            )
            return False
        
        if duration > 60:
            logger.warning(
                f"{name} duration {duration} > 60. Capping at 60."
            )
            return True
        if count > 100000:
             logger.warning(
                 f"{name} count {count} > 100000. Capping at 100000."
             )
             return True
             
        return True

    def _cap_duration_count(self, duration, count, name):
        new_duration = duration
        new_count = count
        if new_duration > 60:
            logger.warning(
                f"{name} duration {new_duration} > 60. Capping at 60."
            )
            new_duration = 60
        if new_count > 100000:
            logger.warning(
                f"{name} count {new_count} > 100000. Capping at 100000."
            )
            new_count = 100000
        return new_duration, new_count

    def _cap_concurrency(self, concurrency, name):
        new_concurrency = concurrency
        if new_concurrency < 10:
            logger.warning(
                f"{name} concurrency {new_concurrency} < 10. Resetting to 10."
            )
            new_concurrency = 10
        if new_concurrency > 1024:
            logger.warning(
                f"{name} concurrency {new_concurrency} > 1024. Capping at 1024."
            )
            new_concurrency = 1024
        return new_concurrency

    def _validate(self):
        self.traffic_dns_duration, self.traffic_dns_count = self._cap_duration_count(
            self.traffic_dns_duration, self.traffic_dns_count, "DNS"
        )
        self.traffic_dns_concurrent = self._cap_concurrency(
            self.traffic_dns_concurrent, "DNS"
        )

        self.traffic_udp_duration, self.traffic_udp_count = self._cap_duration_count(
            self.traffic_udp_duration, self.traffic_udp_count, "UDP"
        )
        self.traffic_udp_concurrent = self._cap_concurrency(
            self.traffic_udp_concurrent, "UDP"
        )

        self.curl_flood_duration, self.curl_flood_count = self._cap_duration_count(
            self.curl_flood_duration, self.curl_flood_count, "HTTPS"
        )
        self.curl_flood_concurrency = self._cap_concurrency(
            self.curl_flood_concurrency, "HTTPS"
        )

        self.ab_duration, self.ab_total_conn = self._cap_duration_count(
            self.ab_duration, self.ab_total_conn, "AB"
        )
        self.ab_concurrent_conn = self._cap_concurrency(
            self.ab_concurrent_conn, "AB"
        )

        self.traffic_dns_enabled = self._validate_traffic_section(
            self.traffic_dns_enabled, 
            self.traffic_dns_duration, 
            self.traffic_dns_count, 
            "DNS"
        )
        
        self.traffic_udp_enabled = self._validate_traffic_section(
            self.traffic_udp_enabled, 
            self.traffic_udp_duration, 
            self.traffic_udp_count, 
            "UDP"
        )
        
        self.curl_flood_enabled = self._validate_traffic_section(
            self.curl_flood_enabled, 
            self.curl_flood_duration, 
            self.curl_flood_count, 
            "HTTPS (CURL)"
        )
        
        if self.ab_total_conn > 0 or self.ab_duration > 0:
             pass 
        else:
             if self.ab_total_conn == 0 and self.ab_duration == 0:
                 if self.ab_duration > 0 and self.ab_total_conn <= 0:
                     self.ab_total_conn = 1
        
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
        if not (180 <= self.client_enable_min <= 600):
            logger.warning("Invalid 'client_enable_min'. Reset to 180.")
            self.client_enable_min = 180
        if not (600 <= self.client_enable_max <= 1200):
            logger.warning("Invalid 'client_enable_max'. Reset to 600.")
            self.client_enable_max = 600
        if self.client_enable_max < self.client_enable_min:
            logger.warning("client_enable_max < min, adjusting to min.")
            self.client_enable_max = self.client_enable_min
        if not (0.0 < self.client_disable_ratio <= 1.0):
            logger.warning("Invalid 'client_disable_ratio'. Reset to 0.15.")
            self.client_disable_ratio = 0.15
        if not (50 <= self.browser_max_memory <= 99):
            logger.warning("Invalid 'browser_max_memory'. Reset to 85.")
            self.browser_max_memory = 85
        if not (1 <= self.browser_max_tabs <= 300):
            logger.warning("Invalid 'browser_max_tabs'. Reset to 20.")
            self.browser_max_tabs = 20
        if self.long_idle_time_max > 7200:
            logger.warning("long_idle_time_max > 7200, capping at 7200.")
            self.long_idle_time_max = 7200
        if self.long_idle_time_min < 300:
            logger.warning("long_idle_time_min < 300, capping at 300.")
            self.long_idle_time_min = 300
        if self.long_idle_time_max < self.long_idle_time_min:
            logger.warning("long_idle_time_max < min, adjusting to min.")
            self.long_idle_time_max = self.long_idle_time_min
        if self.aoac_sleep_interval < 0:
            logger.error("invalid 'aoac_sleep_interval'. Exiting.")
            sys.exit(1)
        if not (60 <= self.aoac_sleep_duration <= 600):
             logger.warning("Invalid 'aoac_sleep_duration'. Resetting to 60.")
             self.aoac_sleep_duration = 60
        if self.ab_total_conn < 0:
             logger.warning("ab_total_conn < 0, disabling (0).")
             self.ab_total_conn = 0
        if self.curl_flood_count < 0:
            self.curl_flood_count = 0
        if self.curl_flood_concurrency < 1:
            self.curl_flood_concurrency = 1