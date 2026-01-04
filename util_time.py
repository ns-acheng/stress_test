import time
import threading

def smart_sleep(duration: float, stop_event: threading.Event) -> bool:
    end_time = time.time() + duration
    while time.time() < end_time:
        if stop_event.is_set():
            return True
        time.sleep(0.5)
    return False
