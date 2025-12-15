import glob
import logging
import os
import shutil
import datetime
from util_subprocess import nsdiag_collect_log

logger = logging.getLogger()
dump_paths = [
        r"C:\dump\stAgentSvc.exe\*.dmp",
        r"C:\ProgramData\netskope\stagent\logs\*.dmp"
    ]

def check_crash_dumps(custom_dump_path: str = "") -> tuple[bool, int]:    
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

def crash_handle(is_64bit: bool, log_dir: str, custom_dump_path: str = ""):
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info("Handling crash: Collecting logs and dumps...")
        
        nsdiag_collect_log(timestamp, is_64bit, log_dir)

        if custom_dump_path:
            dump_paths.append(custom_dump_path)
            
        for path in dump_paths:
            files = glob.glob(path)
            for f in files:
                if os.path.exists(f) and os.path.getsize(f) > 0:
                    try:
                        shutil.copy2(f, log_dir)
                        logger.info(f"Copied dump file {f} to {log_dir}")
                    except Exception as copy_err:
                        logger.error(f"Failed to copy dump {f}: {copy_err}")

    except Exception as e:
        logger.error(f"Error during crash handling: {e}")