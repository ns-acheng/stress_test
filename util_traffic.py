import socket
import random
import string
import time
import concurrent.futures
import subprocess
import os
import logging
import threading
import requests
import ftplib
import io
import paramiko

from util_subprocess import run_batch, run_curl
from util_resources import get_system_memory_usage, log_resource_usage
from util_time import smart_sleep

logger = logging.getLogger()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
}

def _is_stopped(stop_event) -> bool:
    if stop_event is None:
        return False
    return stop_event.is_set()

def read_urls_from_file(filename) -> list[str] | None:
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

def check_url_alive(url) -> str:
    try:
        response = requests.head(
            url, timeout=5, allow_redirects=True, headers=headers
        )
        if response.status_code < 400 or response.status_code == 403:
            if response.url != url:
                logger.info(f"Redirect detected: {url} -> {response.url}")
            
            return response.url
        return ""
    except Exception:
        return ""

def check_urls_and_write_status(urls) -> None:
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
    written_urls = set()

    with open(out_file, 'w', encoding='utf-8') as f:
        for index, url in enumerate(urls):
            if url in existing_urls:
                continue

            alive_url = check_url_alive(url)
            is_alive = bool(alive_url)
            final_url = alive_url if is_alive else url
            status_text = "ALIVE" if is_alive else "DEAD"
            
            logger.info(f"[{index + 1}/{len(urls)}] {url} -> {status_text}")
            
            if is_alive:
                if final_url in existing_urls:
                    logger.info(f"Skipping duplicate final URL (in DB): {final_url}")
                    continue
                if final_url in written_urls:
                    logger.info(f"Skipping duplicate final URL (already written): {final_url}")
                    continue

                f.write(f"{final_url}\n")
                written_urls.add(final_url)
                alive_count += 1
                if (index + 1) % flush_interval == 0:
                    f.flush()

    logger.info(f"Complete. Wrote {alive_count} ALIVE URLs to '{out_file}'.")

def _dns_worker(domain) -> None:
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
) -> None:
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

def _udp_worker(target, port, duration, count, stop_event, family) -> None:
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
) -> None:
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
) -> None:
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
) -> list[str]:
    opened_urls = []
    if not urls:
        logger.warning("No URLs loaded to open.")
        return opened_urls

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
        logger.info(f"Opening batch {batch_cnt + 1} ({len(selected)} URLs)...")
        for u in selected:
            logger.info(f"  -> {u}")

        args = " ".join(selected)
        cmd = os.path.join(tool_dir, f"open_msedge_tabs.bat {args}")
        run_batch(cmd)
        
        opened_urls.extend(selected)

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
    
    return opened_urls

def curl_requests(urls, stop_event=None) -> None:
    if not urls:
        return

    # Ensure first and last URLs are always included
    mandatory = {urls[0], urls[-1]}
    pool = [u for u in urls if u not in mandatory]
    
    count = min(len(urls), 10)
    needed = count - len(mandatory)
    
    selected = list(mandatory)
    if needed > 0 and pool:
        selected.extend(random.sample(pool, min(len(pool), needed)))

    logger.info(f"Running CURL on {len(selected)} URLs (incl. first/last)...")

    for url in selected:
        if _is_stopped(stop_event):
            break
        run_curl(url)
        logger.info(f"CURL with URL: {url}")

def _curl_flood_worker(url) -> str:
    try:
        cmd = ["curl", "-s", "--max-time", "15", "-o", "NUL", url]
        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass
    return url

def generate_curl_flood(
    urls, 
    count, 
    duration=0, 
    concurrency=50, 
    stop_event=None
) -> list[str]:
    all_used_urls = []
    if not urls:
        logger.warning("No URLs for CURL flood.")
        return all_used_urls

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
                _curl_flood_worker(url)

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
        log_buffer = []
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrency
        ) as exe:
            futures = []
            for i in range(1, count + 1):
                if _is_stopped(stop_event):
                    break
                url = random.choice(urls)
                futures.append(exe.submit(_curl_flood_worker, url))
            
            for f in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break
                
                used_url = f.result()
                all_used_urls.append(used_url)
                log_buffer.append(used_url)
                
                if len(log_buffer) >= 100:
                    logger.info("CURL Batch:\n" + "\n".join([f"  -> {u}" for u in log_buffer]))
                    log_buffer = []

                completed += 1
                if completed % milestone == 0:
                    pct = int((completed / count) * 100)
                    logger.info(f"CURL Flood progress: {pct}%")
        
        if log_buffer:
            logger.info("CURL Batch:\n" + "\n".join([f"  -> {u}" for u in log_buffer]))
    
    logger.info("CURL Flood finished.")
    return all_used_urls

class VirtualFile(io.BytesIO):
    def __init__(self, size):
        self._size = size
        self._pos = 0
        super().__init__()

    def read(self, size=-1):
        if self._pos >= self._size:
            return b''
        if size == -1 or size is None:
            size = self._size - self._pos
        else:
            size = min(size, self._size - self._pos)
        
        self._pos += size
        return b'0' * size

    def seek(self, pos, whence=0):
        if whence == 0:
            self._pos = pos
        elif whence == 1:
            self._pos += pos
        elif whence == 2:
            self._pos = self._size + pos
        self._pos = max(0, min(self._pos, self._size))
        return self._pos

    def tell(self):
        return self._pos

def _ftp_worker(target, port, user, password, file_size_mb, is_ftps) -> bool:
    ftp = None
    try:
        if is_ftps:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()
        
        ftp.connect(target, port, timeout=10)
        ftp.login(user, password)
        
        if is_ftps:
            ftp.prot_p()

        filename = f"upload_{random.randint(1000, 9999)}.bin"
        logger.info(f"Generating virtual file {filename} ({file_size_mb} MB)")
        size_bytes = int(file_size_mb * 1024 * 1024)
        vfile = VirtualFile(size_bytes)
        
        ftp.storbinary(f"STOR {filename}", vfile)
        logger.info(f"Uploaded {filename}")
        
        # Delete the file after upload to save disk space on server
        try:
            ftp.delete(filename)
        except Exception:
            pass
            
        ftp.quit()
        return True
    except Exception:
        return False
    finally:
        if ftp:
            try:
                ftp.close()
            except Exception:
                pass

def generate_ftp_traffic(
    target, port, user, password, file_size_mb, 
    count, duration, concurrency, stop_event, is_ftps=False
) -> None:
    protocol = "FTPS" if is_ftps else "FTP"
    msg = f"{protocol} Traffic: {target}:{port}, Size: {file_size_mb}MB"
    if duration > 0:
        msg += f", duration {duration}s"
    else:
        msg += f", count {count}"
    logger.info(msg)

    start_time = time.time()
    end_time = start_time + duration if duration > 0 else 0
    completed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
        futures = []
        
        def _worker_wrapper():
            return _ftp_worker(
                target, port, user, password, file_size_mb, is_ftps
            )

        if duration > 0:
            def _time_worker():
                while time.time() < end_time:
                    if _is_stopped(stop_event): break
                    _worker_wrapper()
            
            for _ in range(concurrency):
                futures.append(exe.submit(_time_worker))
            concurrent.futures.wait(futures)
        else:
            for _ in range(count):
                if _is_stopped(stop_event): break
                futures.append(exe.submit(_worker_wrapper))
            
            for f in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break
                if f.result():
                    completed += 1
                    
    logger.info(f"{protocol} finished. Completed uploads: {completed}")

def generate_ftps_traffic(
    target, port, user, password, file_size_mb, 
    count, duration, concurrency, stop_event
) -> None:
    generate_ftp_traffic(
        target, port, user, password, file_size_mb, 
        count, duration, concurrency, stop_event, is_ftps=True
    )

def _sftp_worker(target, port, user, password, file_size_mb) -> bool:
    transport = None
    sftp = None
    try:
        transport = paramiko.Transport((target, port))
        transport.connect(username=user, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        filename = f"upload_{random.randint(1000, 9999)}.bin"
        logger.info(f"Generating virtual file {filename} ({file_size_mb} MB)")
        size_bytes = int(file_size_mb * 1024 * 1024)
        vfile = VirtualFile(size_bytes)
        
        sftp.putfo(vfile, filename)
        logger.info(f"Uploaded {filename}")
        
        # Delete the file after upload to save disk space on server
        try:
            sftp.remove(filename)
        except Exception:
            pass
            
        return True
    except Exception:
        return False
    finally:
        if sftp: sftp.close()
        if transport: transport.close()

def generate_sftp_traffic(
    target, port, user, password, file_size_mb, 
    count, duration, concurrency, stop_event
) -> None:
    msg = f"SFTP Traffic: {target}:{port}, Size: {file_size_mb}MB"
    if duration > 0:
        msg += f", duration {duration}s"
    else:
        msg += f", count {count}"
    logger.info(msg)

    start_time = time.time()
    end_time = start_time + duration if duration > 0 else 0
    completed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
        futures = []
        
        if duration > 0:
            def _time_worker():
                while time.time() < end_time:
                    if _is_stopped(stop_event): break
                    _sftp_worker(target, port, user, password, file_size_mb)
            
            for _ in range(concurrency):
                futures.append(exe.submit(_time_worker))
            concurrent.futures.wait(futures)
        else:
            for _ in range(count):
                if _is_stopped(stop_event): break
                futures.append(exe.submit(
                    _sftp_worker, target, port, user, password, file_size_mb
                ))
            
            for f in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break
                if f.result():
                    completed += 1

    logger.info(f"SFTP finished. Completed uploads: {completed}")


def get_hostname_from_url(url: str) -> str:
    try:
        hostname = url.strip()
        if hostname.lower().startswith("https://"):
            hostname = hostname[8:]
        elif hostname.lower().startswith("http://"):
            hostname = hostname[7:]
        
        hostname = hostname.split('/')[0]
        hostname = hostname.split(':')[0]
        return hostname
    except Exception:
        return ""