import threading
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import util_traffic
from util_log import LogSetup

def main():
    log_helper = LogSetup()
    logger = log_helper.setup_logging()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    url_file = os.path.join(base_dir, "data", "url.txt")

    if not os.path.exists(url_file):
        logging.error(f"{url_file} not found.")
        return

    urls = util_traffic.read_urls_from_file(url_file)

    if not urls:
        logging.error("No URLs loaded. Please check data/url.txt")
        return

    stop_event = threading.Event()
    logging.info("Starting Standalone CURL Flood. Press Ctrl+C to stop.")

    try:
        util_traffic.generate_curl_flood(urls, 10000, 50, stop_event)
    except KeyboardInterrupt:
        logging.info("Stop signal received.")
        stop_event.set()

if __name__ == "__main__":
    main()
