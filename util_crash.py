import glob
import logging
import os
import shutil
import datetime
import subprocess
from util_subprocess import nsdiag_collect_log

logger = logging.getLogger()

def _get_dump_paths(custom_dump_path: str = "") -> list[str]:
    paths = [
        r"C:\dump\stAgentSvc.exe\*.dmp",
        r"C:\ProgramData\netskope\stagent\logs\*.dmp"
    ]
    if custom_dump_path:
        paths.append(custom_dump_path)
    return paths

def check_crash_dumps(custom_dump_path: str = "") -> tuple[bool, int]:
    dump_paths = _get_dump_paths(custom_dump_path)
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

        dump_paths = _get_dump_paths(custom_dump_path)

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

def generate_live_dump(pid: int, output_dir: str):
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = os.path.join(output_dir, f"LiveDump_{pid}_{timestamp}.dmp")


        cmd = [
            "rundll32.exe",
            "comsvcs.dll",
            "MiniDump",
            str(pid),
            dump_file,
            "full"
        ]

        logger.info(f"Generating live dump for PID {pid} -> {dump_file}")
        subprocess.run(cmd, check=True)

        if os.path.exists(dump_file) and os.path.getsize(dump_file) > 0:
            logger.info("Live dump generated successfully.")
        else:
            logger.error("Live dump file not found or empty.")

    except Exception as e:
        logger.error(f"Failed to generate live dump: {e}")
