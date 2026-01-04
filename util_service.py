import time
import logging
import psutil
import subprocess
from util_crash import generate_live_dump
from util_subprocess import nsdiag_collect_log

logger = logging.getLogger()

def get_service_status(service_name) -> str:
    try:
        status = subprocess.check_output(
            ["sc", "query", service_name],
            encoding='utf-8',
            errors='replace'
        )
        if "RUNNING" in status:
            return "RUNNING"
        elif "STOPPED" in status:
            return "STOPPED"
        elif "STOP_PENDING" in status:
            return "STOP_PENDING"
        elif "START_PENDING" in status:
            return "START_PENDING"
        return "UNKNOWN"
    except subprocess.CalledProcessError:
        return "NOT_FOUND"

def start_service(service_name) -> bool:
    try:
        logger.info(f"Starting service '{service_name}'...")
        subprocess.run(["sc", "start", service_name], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start {service_name}: {e}")
        return False

def stop_service(service_name, timeout=30) -> bool:
    try:
        logger.info(f"Stopping service '{service_name}'...")
        subprocess.run(["sc", "stop", service_name], check=False)

        for _ in range(timeout):
            status = get_service_status(service_name)
            if status == "STOPPED":
                logger.info(f"Service '{service_name}' stopped successfully.")
                return True
            time.sleep(1)

        logger.error(
            f"Error: Timeout. Service '{service_name}' did not stop within {timeout}s."
        )
        return False

    except Exception as e:
        logger.error(f"Exception stopping {service_name}: {e}")
        return False

def _get_pid_by_name(process_name) -> int | None:
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
            return proc.info['pid']
    return None

def handle_non_stop(service_name, is_64bit, log_dir) -> None:
    logger.warning(f"Handling non-stop for '{service_name}'. Waiting extra 60s...")
    for i in range(60):
        status = get_service_status(service_name)
        if status == "STOPPED":
            logger.info(
                f"Service '{service_name}' finally stopped after {i+1}s extra wait."
            )
            return
        time.sleep(1)

    logger.error(
        f"Service '{service_name}' IS STILL RUNNING/HANGING after extra wait."
    )

    proc_name = "stAgentSvc.exe"
    if "stagent" not in service_name.lower():
        proc_name = f"{service_name}.exe"

    pid = _get_pid_by_name(proc_name)
    if pid:
        generate_live_dump(pid, log_dir)
    else:
        logger.error(f"Could not find PID for {proc_name} to dump.")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    nsdiag_collect_log(timestamp, is_64bit, log_dir)

    logger.info("Waiting up to 300s for service to stop...")
    for j in range(300):
        if get_service_status(service_name) == "STOPPED":
            logger.info(
                f"Service '{service_name}' stopped after {j}s post-collection wait."
            )
            return
        time.sleep(1)

    logger.error(
        f"Service '{service_name}' did NOT stop after 300s post-collection wait."
    )
