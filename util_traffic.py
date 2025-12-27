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

def generate_dns_flood(
    domains: list, 
    count: int, 
    duration: float = 0, 
    concurrency: int = 20,
    stop_event: threading.Event = None
):
    if not domains:
        return

    msg = f"DNS flood: {count} queries"
    if duration > 0:
        msg += f", duration {duration}s"
    msg += f", {concurrency} workers"
    logger.info(msg)

    start_time = time.time()
    end_time = start_time + duration if duration > 0 else 0
    
    completed = 0
    milestone = max(1, int(count * 0.2)) if count > 0 else 100

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
        futures = []
        
        def submit_batch(n):
            for _ in range(n):
                dom = random.choice(domains)
                futures.append(exe.submit(_dns_worker, dom))

        if duration > 0:
            pass
        else:
            submit_batch(count)

        if duration > 0:
            def _time_worker():
                while time.time() < end_time:
                    if _is_stopped(stop_event): break
                    _dns_worker(random.choice(domains))
            
            futures = []
            for _ in range(concurrency):
                futures.append(exe.submit(_time_worker))
                
            concurrent.futures.wait(futures)
            
        else:
            for _ in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break
                completed += 1
                if count > 0 and completed % milestone == 0:
                    pct = int((completed / count) * 100)
                    logger.info(f"DNS Flood progress: {pct}%")

def _udp_worker(target, port, duration, count, stop_event, family):
    sock = socket.socket(family, socket.SOCK_DGRAM)
    payload = os.urandom(1024)
    
    start_time = time.time()
    end_time = start_time + duration if duration > 0 else 0
    
    sent = 0
    try:
        while True:
            if _is_stopped(stop_event):
                break
            
            if duration > 0:
                if time.time() >= end_time:
                    break
            elif count > 0:
                if sent >= count:
                    break
            else:
                if sent >= 1:
                    break

            try:
                sock.sendto(payload, (target, port))
                sent += 1
            except Exception:
                pass
    except Exception:
        pass
    finally:
        sock.close()

def generate_udp_flood(
    target: str, 
    port: int, 
    count: int = 0,
    duration: float = 0, 
    concurrency: int = 1,
    stop_event: threading.Event = None, 
    ipv6: bool = False
):
    msg = f"UDP flood -> {target}:{port}"
    if duration > 0:
        msg += f" for {duration}s"
    if count > 0:
        msg += f", limit {count} pkts"
    msg += f", {concurrency} threads (IPv6={ipv6})"
    logger.info(msg)
    
    family = socket.AF_INET6 if ipv6 else socket.AF_INET
    
    threads = []
    count_per_thread = count // concurrency if count > 0 else 0
    
    for i in range(concurrency):
        t = threading.Thread(
            target=_udp_worker, 
            args=(target, port, duration, count_per_thread, stop_event, family)
        )
        t.start()
        threads.append(t)
        
    for t in threads:
        t.join()
        
    logger.info("UDP Flood finished.")

def run_high_concurrency_test(
    target_url: str, 
    requests: int, 
    concurrency: int, 
    tool_dir: str,
    stop_event: threading.Event = None,
    duration: float = 0
):
    ab_path = os.path.join(tool_dir, "ab", "ab.exe")
    if not os.path.exists(ab_path):
        logger.warning(f"AB not found at {ab_path}. Skipping.")
        return

    if duration > 0:
        logger.info(
            f"Run AB: {concurrency} conn -> {target_url} for {duration}s"
        )
        cmd = [
            ab_path, "-t", str(int(duration)), 
            "-n", "2000000000", 
            "-c", str(concurrency), "-k", target_url
        ]
        
        try:
            proc = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                encoding='utf-8',
                errors='replace'
            )
            
            start_time = time.time()
            next_pct = 20
            
            while proc.poll() is None:
                if _is_stopped(stop_event):
                    logger.warning("Stop signal received. Killing AB...")
                    proc.kill()
                    return
                
                elapsed = time.time() - start_time
                if (elapsed / duration) * 100 >= next_pct:
                    logger.info(f"AB Test progress: {next_pct}%")
                    next_pct += 20
                    
                time.sleep(0.5)
                
            proc.communicate()
            if proc.returncode != 0:
                 logger.error(f"AB failed (RC {proc.returncode})")
            else:
                 logger.info("AB finished successfully.")
                 
        except Exception as e:
            logger.error(f"Failed to run AB: {e}")
            
    else:
        batches = 5
        if requests < batches:
            batches = 1
            
        chunk_size = max(1, requests // batches)
        logger.info(
            f"Run AB: {requests} reqs (split {batches}), "
            f"{concurrency} conn -> {target_url}"
        )
        
        for i in range(batches):
            if _is_stopped(stop_event):
                break

            cmd = [
                ab_path, "-n", str(chunk_size), 
                "-c", str(concurrency), "-k", target_url
            ]
            
            try:
                proc = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    encoding='utf-8',
                    errors='replace'
                )
                
                while proc.poll() is None:
                    if _is_stopped(stop_event):
                        logger.warning("Stop signal received. Killing AB...")
                        proc.kill()
                        return
                    time.sleep(0.5)
                    
                proc.communicate()
                
                if proc.returncode != 0:
                    logger.error(f"AB batch {i+1} failed (RC {proc.returncode})")
                else:
                    pct = int(((i + 1) / batches) * 100)
                    logger.info(f"AB Test progress: {pct}%")
                    
            except Exception as e:
                logger.error(f"Failed to run AB batch {i+1}: {e}")

        logger.info("AB finished successfully.")

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

def _curl_flood_worker(url, seq):
    if seq > 0 and seq % 100 == 0:
        logger.info(f"Req #{seq}: {url}")
    try:
        cmd = ["curl", "-s", "-o", "NUL", url]
        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def generate_curl_flood(
    urls, 
    count, 
    duration=0, 
    concurrency=50, 
    stop_event=None
):
    if not urls:
        logger.warning("No URLs for CURL flood.")
        return

    msg = f"Start CURL Flood: {concurrency} workers"
    if duration > 0:
        msg += f", duration {duration}s"
    else:
        msg += f", {count} reqs"
    logger.info(msg)

    if duration > 0:
        end_time = time.time() + duration
        
        def _time_worker():
            while time.time() < end_time:
                if _is_stopped(stop_event): break
                url = random.choice(urls)
                _curl_flood_worker(url, 0)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrency
        ) as exe:
            futures = []
            for _ in range(concurrency):
                futures.append(exe.submit(_time_worker))
            concurrent.futures.wait(futures)
            
    else:
        milestone = max(1, int(count * 0.2))
        completed = 0
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrency
        ) as exe:
            futures = []
            for i in range(1, count + 1):
                if _is_stopped(stop_event):
                    break
                url = random.choice(urls)
                futures.append(exe.submit(_curl_flood_worker, url, i))
            
            for f in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break
                
                completed += 1
                if completed % milestone == 0:
                    pct = int((completed / count) * 100)
                    logger.info(f"CURL Flood progress: {pct}%")
    
    logger.info("CURL Flood finished.")