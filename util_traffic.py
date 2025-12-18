import socket
import random
import string
import time
import concurrent.futures
import subprocess
import os
import logging
import threading
import sys
import requests
from util_subprocess import run_batch, run_curl
from util_resources import get_system_memory_usage, log_resource_usage
from util_time import smart_sleep

logger = logging.getLogger()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
}

def _is_stopped(stop_event):
    if stop_event is None:
        return False
    return stop_event.is_set()

def read_urls_from_file(filename):
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    urls.append(line.strip())
        return urls
    except FileNotFoundError:
        logger.error(f"Error: The file '{filename}' was not found.")
        return None

def check_url_alive(url):
    try:
        response = requests.head(
            url, timeout=5, allow_redirects=True, headers=headers
        )
        return response.status_code < 400 or response.status_code == 403
    except Exception:
        return False

def check_urls_and_write_status(urls):
    if not urls:
        return

    existing_urls = set()
    target_check_file = r'data\url.txt'
    
    if os.path.exists(target_check_file):
        try:
            with open(target_check_file, 'r', encoding='utf-8') as f:
                existing_urls = {line.strip() for line in f if line.strip()}
        except FileNotFoundError:
            pass

    out_file = r'data\url_alive.txt'
    flush_interval = 50
    alive_count = 0

    with open(out_file, 'w') as f:
        for index, url in enumerate(urls):
            if url in existing_urls:
                continue

            is_alive = check_url_alive(url)
            status_text = "ALIVE" if is_alive else "DEAD"
            print(f"[{index + 1}/{len(urls)}] {url} -> {status_text}")
            sys.stdout.flush()
            
            if is_alive:
                f.write(f"{url}\n")
                alive_count += 1
                if (index + 1) % flush_interval == 0:
                    f.flush()

    print(f"\nComplete. Wrote {alive_count} ALIVE URLs to '{out_file}'.")

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
    stop_event: threading.Event = None, 
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
            if _is_stopped(stop_event):
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
    stop_event: threading.Event = None
):
    ab_path = os.path.join(tool_dir, "ab", "ab.exe")
    if not os.path.exists(ab_path):
        logger.warning(f"AB not found at {ab_path}. Skipping.")
        return

    cmd = [
        ab_path, "-n", str(requests), "-c", str(concurrency), "-k", target_url
    ]
    
    logger.info(f"Run AB: {requests} reqs, {concurrency} conn -> {target_url}")
    
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        while proc.poll() is None:
            if _is_stopped(stop_event):
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

def open_browser_tabs(
    urls, tool_dir, max_tabs, max_mem, stop_event, log_dir, wait_sec
):
    if not urls:
        logger.warning("No URLs loaded to open.")
        return

    logger.info(
        f"Start tab loop. Max Mem: {max_mem}%, Max Tabs: {max_tabs}"
    )

    batch_cnt = 0
    total_tabs = 0
    batch_limit = 30

    while batch_cnt < batch_limit:
        if _is_stopped(stop_event):
            break
        if total_tabs >= max_tabs:
            logger.info(f"Max tabs ({total_tabs}). Stop opening.")
            break

        remaining = max_tabs - total_tabs
        count = min(len(urls), 10)
        count = min(count, remaining)

        if count <= 0:
            break

        selected = random.sample(urls, count)
        logger.info(f"Opening batch {batch_cnt + 1} ({count} URLs)...")

        args = " ".join(selected)
        cmd = os.path.join(tool_dir, f"open_msedge_tabs.bat {args}")
        run_batch(cmd)

        total_tabs += count
        if smart_sleep(wait_sec, stop_event):
            break
        log_resource_usage("stAgentSvc.exe", log_dir)

        mem = get_system_memory_usage() * 100.0
        logger.info(f"System Mem: {mem:.2f}% (Target: {max_mem}%)")

        if mem >= max_mem:
            logger.info(f"Threshold reached ({mem:.2f}%).")
            break

        batch_cnt += 1

    if batch_cnt >= batch_limit:
        logger.warning(f"Reached max batch limit ({batch_limit})")

def curl_requests(urls, stop_event=None):
    if not urls:
        return

    count = min(len(urls), 10)
    selected = random.sample(urls, count)
    logger.info(f"Running CURL on {count} random URLs...")

    for url in selected:
        if _is_stopped(stop_event):
            break
        run_curl(url)
        logger.info(f"CURL with URL: {url}")

def _curl_flood_worker(url):
    try:
        cmd = ["curl", "-s", "-o", "NUL", url]
        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def generate_curl_flood(urls, count, concurrency, stop_event=None):
    if not urls:
        logger.warning("No URLs for CURL flood.")
        return

    logger.info(f"Start CURL Flood: {count} reqs, {concurrency} workers.")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
        futures = []
        for _ in range(count):
            if _is_stopped(stop_event):
                break
            url = random.choice(urls)
            futures.append(exe.submit(_curl_flood_worker, url))
        
        for f in concurrent.futures.as_completed(futures):
            if _is_stopped(stop_event):
                exe.shutdown(wait=False, cancel_futures=True)
                break
    
    logger.info("CURL Flood finished.")