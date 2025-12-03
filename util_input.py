import threading
import time
import msvcrt
import logging

logger = logging.getLogger()

def start_input_monitor(stop_event: threading.Event):
    def _monitor():
        logger.info("Input monitor started. Press ESC or Ctrl+C to stop.")
        while not stop_event.is_set():
            if msvcrt.kbhit():
                try:
                    key = msvcrt.getch()
                    if key == b'\x1b' or key == b'\x03':
                        logger.warning("Stop signal detected. Stopping...")
                        stop_event.set()
                        break
                except Exception:
                    pass
            time.sleep(0.1)

    th = threading.Thread(target=_monitor, daemon=True)
    th.start()