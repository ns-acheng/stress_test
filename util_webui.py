import sys
import os
import logging

# Add sibling repo 'pylark-webapi-lib/src' to sys.path
#   parent/
#     stress_test/ (current repo)
#     pylark-webapi-lib/ (sibling repo)
#       src/
#         webapi/
current_dir = os.path.dirname(os.path.abspath(__file__))
sibling_repo_path = os.path.abspath(os.path.join(current_dir, "..", "pylark-webapi-lib", "src"))

if os.path.exists(sibling_repo_path):
    if sibling_repo_path not in sys.path:
        sys.path.append(sibling_repo_path)
else:
    # Fallback: Try looking for a 'lib' folder inside stress_test (for portable deployments)
    local_lib_path = os.path.join(current_dir, "lib", "pylark-webapi-lib", "src")
    if os.path.exists(local_lib_path):
        if local_lib_path not in sys.path:
            sys.path.append(local_lib_path)

try:
    from webapi import WebAPI
    from webapi.auth import Authentication
    from webapi.settings.security_cloud_platform.netskope_client.client_configuration import ClientConfiguration
    from webapi.settings.security_cloud_platform.traffic_steering.steering_configuration import SteeringConfiguration
except ImportError:
    logging.getLogger(__name__).warning("Failed to import pylark-webapi-lib. WebUI features will be unavailable.")
    WebAPI = None

logger = logging.getLogger(__name__)

class WebUIClient:
    def __init__(self, hostname, username, password):
        if not WebAPI:
            raise ImportError("pylark-webapi-lib not found")
        
        self.hostname = hostname
        self.username = username
        self.password = password
        self.webapi = None
        self.is_logged_in = False

    def login(self):
        try:
            logger.info(f"Connecting to WebUI {self.hostname} as {self.username}")
            self.webapi = WebAPI(hostname=self.hostname, username=self.username, password=self.password)
            auth = Authentication(self.webapi)
            auth.login()
            self.is_logged_in = True
            logger.info("WebUI Login successful")
            return True
        except Exception as e:
            logger.error(f"WebUI Login failed: {e}")
            self.is_logged_in = False
            return False

    def update_client_config(self, config_name="Default tenant config", **kwargs):
        """
        Updates Client Configuration.
        Example kwargs: onpremcheck=1, onprem_use_dns=0, onprem_http_host="http://googleapi.com"
        """
        if not self.is_logged_in:
            if not self.login():
                return False

        try:
            client_config = ClientConfiguration(self.webapi)
            logger.info(f"Updating client configuration '{config_name}' with {kwargs}")

            if 'search_config' not in kwargs:
                kwargs['search_config'] = config_name

            response = client_config.update_client_config(**kwargs)
            
            if response.get('status') == 'success':
                logger.info("Client Config Update successful!")
                return True
            else:
                logger.error(f"Client Config Update failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"An error occurred during Client Config update: {e}")
            return False

    def update_steering_config(self, config_name="Default tenant config", traffic_mode=None, exception_domains=None):
        """
        Updates Steering Configuration.
        traffic_mode: "web", "all", etc.
        exception_domains: list of strings ["example.com"]
        """
        if not self.is_logged_in:
            if not self.login():
                return False

        try:
            steering_config = SteeringConfiguration(self.webapi)
            
            if traffic_mode:
                logger.info(f"Updating traffic steering mode to '{traffic_mode}' for '{config_name}'")
                steering_config.update_traffic_steering_mode(
                    traffic_mode=traffic_mode,
                    config_name=config_name
                )

            if exception_domains:
                logger.info(f"Adding exception domains to '{config_name}': {exception_domains}")
                steering_config.add_exception_domains(
                    domain_list=exception_domains,
                    config_name=config_name
                )
            
            return True

        except Exception as e:
            logger.error(f"An error occurred during Steering Config update: {e}")
            return False

def perform_onprem_setup(config):
    client_toggles = config.get("client_feature_toggling", {})
    webui_cfg = client_toggles.get("webui_login", {})
    onprem_cfg = client_toggles.get("on_prem", {})

    if not onprem_cfg.get("enable", 0):
        return

    hostname = webui_cfg.get("hostname", "")
    username = webui_cfg.get("username", "")
    password = webui_cfg.get("password", "")

    if "://" in hostname:
        from urllib.parse import urlparse
        hostname = urlparse(hostname).netloc

    client = WebUIClient(hostname, username, password)
    if client.login():
        use_dns = onprem_cfg.get("onprem_use_dns", 0)
        http_host = onprem_cfg.get("onprem_http_host", "")
        
        client.update_client_config(
            onpremcheck=1,
            onprem_use_dns=int(use_dns),
            onprem_http_host=http_host
        )
        return True
    
    return False

if __name__ == "__main__":
    hostname = 'ac-stg01.stg.boomskope.com'
    username = 'acheng@netskope.com'
    password = 'N3tskope!'

    client = WebUIClient(hostname, username, password)
    if client.login():
        print("Login successful.")
        client.update_client_config(
            onpremcheck=1,
            onprem_use_dns=0,
            onprem_http_host="http://googleapi.com"
        )
        client.update_steering_config(
            traffic_mode="all"
        )
    else:
        print("Login failed.")
