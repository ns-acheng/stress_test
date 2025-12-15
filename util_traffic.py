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
    tool_dir: str,
    stop_event: threading.Event
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
        proc = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        while proc.poll() is None:
            if stop_event.is_set():
                logger.warning("Stop signal received. Killing AB...")
                proc.kill()
                return
            time.sleep(0.5)
            
        stdout, stderr = proc.communicate()
        
        if proc.returncode != 0:
            err = stderr.strip()[:200]
            logger.error(f"AB failed (RC {proc.returncode}): {err}")
        else:
            logger.info("AB finished successfully.")
            
    except Exception as e:
        logger.error(f"Failed to run AB: {e}")