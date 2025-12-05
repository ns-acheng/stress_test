import glob
import logging
import os

logger = logging.getLogger()

def check_crash_dumps(custom_dump_path: str = "") -> tuple[bool, int]:
    dump_paths = [
        r"C:\dump\stAgentSvc.exe\*.dmp",
        r"C:\ProgramData\netskope\stagent\logs\*.dmp"
    ]
    if custom_dump_path:
        dump_paths.append(custom_dump_path)

    found = False
    zero_count = 0

    for path in dump_paths:
        files = glob.glob(path)
        for f in files:
            try:
                size = os.path.getsize(f)
                if size == 0:
                    logger.warning(f"Ignored 0-byte dump file: {f}")
                    try:
                        os.remove(f)
                        logger.info(f"Deleted 0-byte dump file: {f}")
                        zero_count += 1
                    except OSError as os_err:
                        logger.error(f"Failed to delete 0-byte dump {f}: {os_err}")
                    continue
                
                logger.error(f"CRASH DUMP DETECTED: {f} (Size: {size} bytes)")
                found = True
            except Exception as e:
                logger.error(f"Error checking file {f}: {e}")
                
    return found, zero_count