import glob
import logging

logger = logging.getLogger()

def check_crash_dumps(custom_dump_path: str = "") -> bool:
    dump_paths = [
        r"C:\dump\stAgentSvc.exe\*.dmp",
        r"C:\ProgramData\netskope\stagent\logs\*.dmp"
    ]
    if custom_dump_path:
        dump_paths.append(custom_dump_path)

    found = False
    for path in dump_paths:
        files = glob.glob(path)
        if files:
            logger.error(f"CRASH DUMP DETECTED at: {path}")
            for f in files:
                logger.error(f"File: {f}")
            found = True
    return found