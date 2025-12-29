import json
import sys
import logging

logger = logging.getLogger()

class ToolConfig:
    TRAFFIC_MAP = [
        {
            "json_key": "dns",
            "enable_attr": "dns_enabled",
            "fields": {
                "count": "dns_count",
                "duration_sec": "dns_duration",
                "concurrent_conn": "dns_concurrent"
            }
        },
        {
            "json_key": "udp",
            "enable_attr": "udp_enabled",
            "fields": {
                "count": "udp_count",
                "duration_sec": "udp_duration",
                "concurrent_conn": "udp_concurrent",
                "target_ip": "udp_target_ip",
                "target_ipv6": "udp_target_ipv6",
                "target_port": "udp_target_port"
            }
        },
        {
            "json_key": "https",
            "enable_attr": "curl_flood_enabled",
            "fields": {
                "count": "curl_flood_count",
                "duration_sec": "curl_flood_duration",
                "concurrent_conn": "curl_flood_concurrent"
            }
        }
    ]

    # Validation Rules: (Attribute, Min, Max, Default)
    RANGE_CONSTRAINTS = [
        ("client_enable_min", 180, 600, 180),
        ("client_enable_max", 600, 1200, 600),
        ("client_disable_ratio", 0.00001, 1.0, 0.15),
        ("browser_max_memory", 50, 99, 85),
        ("browser_max_tabs", 1, 300, 20),
        ("aoac_sleep_duration", 60, 600, 60),
        ("long_idle_time_min", 300, 7200, 300),
        ("long_idle_time_max", 300, 7200, 300)
    ]

    # Traffic Validation: (Name, DurationAttr, CountAttr, ConcurrencyAttr, EnabledAttr)
    TRAFFIC_VALIDATION = [
        ("DNS", "dns_duration", "dns_count", 
         "dns_concurrent", "dns_enabled"),
        ("UDP", "udp_duration", "udp_count", 
         "udp_concurrent", "udp_enabled"),
        ("HTTPS", "curl_flood_duration", "curl_flood_count", 
         "curl_flood_concurrent", "curl_flood_enabled"),
        ("AB", "ab_duration", "ab_total_conn", "ab_concurrent", None)
    ]

    def __init__(self, config_file: str):
        self.config_file = config_file

        self.loop_times = 1000
        self.stop_svc_interval = 1
        self.stop_drv_interval = 0
        self.custom_dump_path = ""

        self.failclose_enabled = True
        self.failclose_interval = 20

        self.client_disabling_enabled = False
        self.client_enable_min = 180
        self.client_enable_max = 600
        self.client_disable_ratio = 0.15

        self.aoac_sleep_enabled = False
        self.aoac_sleep_interval = 0
        self.aoac_sleep_duration = 60

        self.long_idle_interval = 0
        self.long_idle_time_min = 300
        self.long_idle_time_max = 300

        self.enable_browser_tabs_open = 1
        self.browser_max_memory = 85
        self.browser_max_tabs = 20

        self.dns_enabled = False
        self.dns_count = 500
        self.dns_duration = 0
        self.dns_concurrent = 20

        self.udp_enabled = False
        self.udp_target_ip = "127.0.0.1"
        self.udp_target_ipv6 = ""
        self.udp_target_port = 8080
        self.udp_duration = 10
        self.udp_count = 0
        self.udp_concurrent = 1

        self.ab_total_conn = 10000
        self.ab_concurrent = 0
        self.ab_duration = 0
        self.ab_target_urls = ["https://google.com"]

        self.curl_flood_enabled = False
        self.curl_flood_count = 1000
        self.curl_flood_duration = 0
        self.curl_flood_concurrent = 50

    def load(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {self.config_file}")

            self.loop_times = config.get('loop_times', self.loop_times)
            self.stop_svc_interval = config.get('stop_svc_interval', self.stop_svc_interval)
            self.stop_drv_interval = config.get('stop_drv_interval', self.stop_drv_interval)
            self.custom_dump_path = config.get('custom_dump_path', self.custom_dump_path)
            self.long_idle_interval = config.get('long_idle_interval', self.long_idle_interval)
            self.long_idle_time_min = config.get('long_idle_time_min', self.long_idle_time_min)
            self.long_idle_time_max = config.get('long_idle_time_max', self.long_idle_time_max)

            cft = config.get('client_feature_toggling', {})

            fc = cft.get('failclose', {})
            self.failclose_enabled = bool(fc.get('enable', self.failclose_enabled))
            self.failclose_interval = fc.get('interval', self.failclose_interval)

            cd = cft.get('client_disabling', {})
            self.client_disabling_enabled = bool(cd.get('enable', self.client_disabling_enabled))
            self.client_enable_min = cd.get('enable_sec_min', self.client_enable_min)
            self.client_enable_max = cd.get('enable_sec_max', self.client_enable_max)
            self.client_disable_ratio = cd.get('disable_ratio', self.client_disable_ratio)

            aoac = cft.get('aoac_sleep', {})
            self.aoac_sleep_enabled = bool(aoac.get('enable', self.aoac_sleep_enabled))
            self.aoac_sleep_interval = aoac.get('interval', self.aoac_sleep_interval)
            self.aoac_sleep_duration = aoac.get('duration_sec', self.aoac_sleep_duration)

            tg = config.get('traffic_gen', {})
            browser = tg.get('browser', {})
            self.enable_browser_tabs_open = browser.get('enable', self.enable_browser_tabs_open)
            self.browser_max_memory = browser.get('max_memory', self.browser_max_memory)
            self.browser_max_tabs = browser.get('max_tabs', self.browser_max_tabs)

            for proto in self.TRAFFIC_MAP:
                section = tg.get(proto['json_key'], {})
                current_enabled = getattr(self, proto['enable_attr'])
                setattr(self, proto['enable_attr'], bool(section.get('enable', current_enabled)))
                
                for json_field, attr_name in proto['fields'].items():
                    current_val = getattr(self, attr_name)
                    setattr(self, attr_name, section.get(json_field, current_val))

            ab = tg.get('ab', {})
            ab_enabled = ab.get('enable', 1)
            self.ab_concurrent = ab.get('concurrent_conn', self.ab_concurrent)
            self.ab_duration = ab.get('duration_sec', self.ab_duration)
            
            if not ab_enabled:
                self.ab_total_conn = 0
                self.ab_duration = 0
            
            self.ab_target_urls = ab.get('target_urls', self.ab_target_urls)
            if not isinstance(self.ab_target_urls, list):
                if self.ab_target_urls:
                    self.ab_target_urls = [self.ab_target_urls]
                else:
                    self.ab_target_urls = ["https://google.com"]

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
        if self.aoac_sleep_interval < 0:
            logger.error("invalid 'aoac_sleep_interval'. Exiting.")
            sys.exit(1)

        for attr, min_val, max_val, default in self.RANGE_CONSTRAINTS:
            val = getattr(self, attr)
            if not (min_val <= val <= max_val):
                logger.warning(f"Invalid '{attr}' ({val}). Reset to {default}.")
                setattr(self, attr, default)

        if self.client_enable_max < self.client_enable_min:
            logger.warning("client_enable_max < min, adjusting to min.")
            self.client_enable_max = self.client_enable_min
            
        if self.long_idle_time_max < self.long_idle_time_min:
            logger.warning("long_idle_time_max < min, adjusting to min.")
            self.long_idle_time_max = self.long_idle_time_min

        for name, dur_attr, count_attr, conc_attr, enabled_attr in self.TRAFFIC_VALIDATION:
            if enabled_attr and not getattr(self, enabled_attr):
                continue
                
            dur = getattr(self, dur_attr)
            count = getattr(self, count_attr)
            conc = getattr(self, conc_attr)
            
            new_dur, new_count = self._cap_duration_count(dur, count, name)
            setattr(self, dur_attr, new_dur)
            setattr(self, count_attr, new_count)
            
            new_conc = self._cap_concurrency(conc, name)
            setattr(self, conc_attr, new_conc)
            
            if enabled_attr:
                is_valid = self._validate_traffic_section(True, new_dur, new_count, name)
                setattr(self, enabled_attr, is_valid)
            else:
                if new_dur <= 0 and new_count <= 0:
                     pass

        if self.ab_total_conn == 0 and self.ab_duration == 0:
             pass
             
        if self.ab_duration > 0 and self.ab_total_conn <= 0:
             self.ab_total_conn = 1

    def _validate_traffic_section(self, enabled, duration, count, name):
        if not enabled:
            return False
        if duration <= 0 and count <= 0:
            logger.warning(f"Both duration and count are 0 for {name}. Disabling.")
            return False
        return True

    def _cap_duration_count(self, duration, count, name):
        new_duration = duration
        new_count = count
        if new_duration > 60:
            logger.warning(f"{name} duration {new_duration} > 60. Capping at 60.")
            new_duration = 60
        if new_count > 100000:
            logger.warning(f"{name} count {new_count} > 100000. Capping at 100000.")
            new_count = 100000
        return new_duration, new_count

    def _cap_concurrency(self, concurrency, name):
        new_concurrency = concurrency
        if new_concurrency < 10:
            logger.warning(f"{name} concurrency {new_concurrency} < 10. Resetting to 10.")
            new_concurrency = 10
        if new_concurrency > 1024:
            logger.warning(f"{name} concurrency {new_concurrency} > 1024. Capping at 1024.")
            new_concurrency = 1024
        return new_concurrency