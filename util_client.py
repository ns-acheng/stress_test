import random
import logging
from util_service import get_service_status
from util_subprocess import nsdiag_enable_client
from util_time import smart_sleep

logger = logging.getLogger()

def _wait_interval(duration, stop_event):
    steps = duration // 2
    remainder = duration % 2
    for _ in range(steps):
        if smart_sleep(2, stop_event): return True
    if remainder > 0:
        if smart_sleep(remainder, stop_event): return True
    return False

def client_toggler_loop(stop_event, service_name, is_64bit):
    logger.info("Client Toggle Thread Started.")
    while not stop_event.is_set():
        run_time = random.randint(180, 300)
        if _wait_interval(run_time, stop_event): break
        
        if get_service_status(service_name) != "RUNNING":
            logger.info("Client Toggle Thread: Skip toggle - service not running.")
            continue

        logger.info("Client Toggle Thread: Disabling Client...")
        nsdiag_enable_client(False, is_64bit)
        
        disable_time = random.randint(90, 150)
        if _wait_interval(disable_time, stop_event): break

        if get_service_status(service_name) == "RUNNING":
            logger.info("Client Toggle Thread: Enabling Client...")
            nsdiag_enable_client(True, is_64bit)