import threading
import logging
import sys
import os
import util_traffic

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    url_file = r"data\url.txt"
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