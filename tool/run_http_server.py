import argparse
import logging
import os
import sys
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from util_input import start_input_monitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):

        logger.info("%s - - [%s] %s" %
                    (self.client_address[0],
                     self.log_date_time_string(),
                     format % args))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--directory", type=str, default=".")
    args = parser.parse_args()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)


    handler_class = partial(QuietHandler, directory=os.path.abspath(args.directory))

    try:
        server = ThreadingHTTPServer(('0.0.0.0', args.port), handler_class)
    except PermissionError:
        logger.error(f"Permission denied binding to port {args.port}. Try running as Admin or use a port > 1024.")
        return
    except OSError as e:
        logger.error(f"Failed to start server: {e}")
        return

    logger.info(f"HTTP Server running on port {args.port}")
    logger.info(f"Serving directory: {os.path.abspath(args.directory)}")
    logger.info("Press ESC to stop the server")

    stop_event = threading.Event()
    start_input_monitor(stop_event)


    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Stopping HTTP server...")
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    main()
