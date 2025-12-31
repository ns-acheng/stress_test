import os
import re
import logging
import threading
import codecs
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse
from util_time import smart_sleep

logger = logging.getLogger(__name__)

class NsClientLogValidator:
    def __init__(self):
        self.prog_data = os.environ.get('ProgramData', 'C:\\ProgramData')
        self.stagent_path = os.path.join(self.prog_data, 'netskope', 'stagent')

        self.log_path = os.path.join(
            self.stagent_path, 'logs', 'nsdebuglog.log'
        )
        
        self.rotated_log_path = self.log_path.replace('.log', '.1.log')
        self.lock = threading.Lock()
        self.last_pos = 0
        self.last_inode = 0
        self.pending_reads = [] # List of (inode, start_pos)

    def get_steering_config(self):
        json_path = os.path.join(self.stagent_path, 'data', 'nssteering.json')
        if not os.path.exists(json_path):
            return {}
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load steering config: {e}")
            return {}

    def update_pos_to_end(self):
        with self.lock:
            if os.path.exists(self.log_path):
                try:
                    self.last_pos = os.path.getsize(self.log_path)
                except OSError:
                    self.last_pos = 0

    def update_pos_with_time_buffer(self, seconds=100):
        with self.lock:
            self.pending_reads = []
            target_time = datetime.now() - timedelta(seconds=seconds)
            
            # Helper to scan a file backwards for timestamp < target_time
            def scan_file(filepath):
                if not os.path.exists(filepath):
                    return None, 0, 0
                try:
                    st = os.stat(filepath)
                    fsize = st.st_size
                    inode = st.st_ino
                    if fsize == 0: return None, 0, inode
                    
                    chunk_size = 1024 * 1024 # 1MB
                    pos = fsize
                    min_pos = max(0, fsize - (50 * 1024 * 1024)) # Max 50MB scan
                    
                    while pos > min_pos:
                        read_len = min(chunk_size, pos - min_pos)
                        pos -= read_len
                        try:
                            with open(filepath, 'rb') as f:
                                f.seek(pos)
                                chunk = f.read(read_len)
                                text = chunk.decode('utf-8', errors='ignore')
                                match = re.search(
                                    r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})', 
                                    text
                                )
                                if match:
                                    ts_str = match.group(1)
                                    try:
                                        ts = datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S')
                                        if ts < target_time:
                                            return True, pos, inode
                                    except ValueError:
                                        pass
                        except Exception:
                            break
                    return False, pos, inode
                except OSError:
                    return None, 0, 0

            # 1. Check current log
            found, pos, inode = scan_file(self.log_path)
            if found:
                self.last_pos = pos
                self.last_inode = inode
                logger.info(f"Log seek: Found logs older than {seconds}s in current log at {pos}")
                return

            # 2. Check rotated logs .1 to .10
            rotated_files = []
            for i in range(1, 11):
                p = self.log_path.replace('.log', f'.{i}.log')
                if os.path.exists(p):
                    rotated_files.append(p)
                else:
                    break
            
            found_idx = -1
            found_pos = 0
            
            # Scan rotated files to find start point
            for idx, fpath in enumerate(rotated_files):
                found, pos, inode = scan_file(fpath)
                if found is not None: # File exists
                    if found: # Found timestamp < target
                        found_idx = idx
                        found_pos = pos
                        break
            
            # Queue files based on finding
            files_to_queue = []
            if found_idx != -1:
                files_to_queue.append((rotated_files[found_idx], found_pos))
                for i in range(found_idx - 1, -1, -1):
                    files_to_queue.append((rotated_files[i], 0))
            else:
                if rotated_files:
                    for i in range(len(rotated_files) - 1, -1, -1):
                        files_to_queue.append((rotated_files[i], 0))
            
            # Store inodes for pending reads
            for fpath, start_pos in files_to_queue:
                try:
                    ino = os.stat(fpath).st_ino
                    self.pending_reads.append((ino, start_pos))
                except OSError:
                    pass
            
            # Set state for current log (to be read after pending)
            try:
                st = os.stat(self.log_path)
                self.last_inode = st.st_ino
                self.last_pos = 0
            except OSError:
                self.last_inode = 0
                self.last_pos = 0
                
            logger.info(f"Log seek: Queued {len(self.pending_reads)} pending files based on inodes.")

    def _read_chunk(self, filepath, start_pos):
        if not os.path.exists(filepath):
            return ""
        try:
            with codecs.open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(start_pos)
                content = f.read()
                return content
        except Exception as e:
            logger.error(f"Failed to read log {filepath}: {e}")
            return ""

    def check_log(self, pattern, flags=0, is_regex=True):
        with self.lock:
            found = False
            current_size = 0
            if os.path.exists(self.log_path):
                try:
                    current_size = os.path.getsize(self.log_path)
                except OSError:
                    current_size = 0
            
            if current_size < self.last_pos:
                content_old = self._read_chunk(self.rotated_log_path, self.last_pos)
                if is_regex:
                    if re.search(pattern, content_old, flags=flags):
                        found = True
                elif pattern in content_old:
                    found = True
                self.last_pos = 0
                
            content_new = self._read_chunk(self.log_path, self.last_pos)
            if not found:
                if is_regex:
                    if re.search(pattern, content_new, flags=flags):
                        found = True
                elif pattern in content_new:
                    found = True
            
            if os.path.exists(self.log_path):
                self.last_pos = os.path.getsize(self.log_path)
            else:
                self.last_pos = 0
            return found

    def read_new_logs(self):
        with self.lock:
            content = ""

            def find_file_by_inode(target_inode):
                # Check current
                try:
                    if os.stat(self.log_path).st_ino == target_inode:
                        return self.log_path
                except OSError: pass
                # Check rotated
                for i in range(1, 11):
                    p = self.log_path.replace('.log', f'.{i}.log')
                    if os.path.exists(p):
                        try:
                            if os.stat(p).st_ino == target_inode:
                                return p
                        except OSError: pass
                return None

            # 1. Read pending files (historical/rotated) by inode
            if self.pending_reads:
                for inode, start_pos in self.pending_reads:
                    fpath = find_file_by_inode(inode)
                    if fpath:
                        chunk = self._read_chunk(fpath, start_pos)
                        content += chunk
                self.pending_reads = []

            # 2. Read current log with inode tracking
            try:
                st = os.stat(self.log_path)
                current_inode = st.st_ino
                current_size = st.st_size
            except OSError:
                return content

            if self.last_inode != 0 and current_inode != self.last_inode:
                # Rotation detected! Find where last_inode went
                old_path = find_file_by_inode(self.last_inode)
                if old_path:
                    content += self._read_chunk(old_path, self.last_pos)
                
                # Reset for new file
                self.last_pos = 0
                self.last_inode = current_inode

            # Read current file
            if current_size < self.last_pos:
                # Truncated or reset without inode change (unlikely but possible)
                self.last_pos = 0
            
            chunk = self._read_chunk(self.log_path, self.last_pos)
            content += chunk
            
            # Update state
            if os.path.exists(self.log_path):
                try:
                    st = os.stat(self.log_path)
                    self.last_pos = st.st_size
                    self.last_inode = st.st_ino
                except OSError:
                    pass
            
            if content:
                preview_start = content[:100].replace('\r', '\\r').replace('\n', '\\n')
                preview_end = content[-100:].replace('\r', '\\r').replace('\n', '\\n')
                logger.info(f"Log Reader: Read {len(content)} bytes. Start: '{preview_start}'")
                logger.info(f"Log Reader: End: '{preview_end}'")
            
            return content

_validator = None
_validator_lock = threading.Lock()

def get_validator():
    global _validator
    with _validator_lock:
        if _validator is None:
            _validator = NsClientLogValidator()
    return _validator

def get_steering_config():
    return get_validator().get_steering_config()

def check_nsclient_log(pattern):
    validator = get_validator()
    return validator.check_log(pattern, is_regex=False)

def check_nsclient_log_regex(pattern, flags=0):
    validator = get_validator()
    return validator.check_log(pattern, flags=flags, is_regex=True)

def check_tunneling_in_text(process_name, url, text):
    if not url or not text:
        return False
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            if "://" not in url:
                host = url.split("/")[0].split(":")[0]
        
        if not host:
            return True 

        # Pattern 1: Tunneling flow
        pat_tunnel = (
            r"Tunneling flow from addr: .*, process: " + 
            re.escape(process_name) + 
            r" to host: " + re.escape(host) + r"(,|:)"
        )
        
        # Pattern 2: Bypassing flow (exception host)
        pat_bypass = (
            r"bypassing flow to exception host: " + 
            re.escape(host) + 
            r", process: " + re.escape(process_name)
        )

        if re.search(pat_tunnel, text) or re.search(pat_bypass, text):
            return True
        return False
    except Exception:
        return False

def validate_traffic_flow(process_map, stop_event):
    # process_map: {"msedge.exe": [url1, url2], "curl.exe": [url3, url4]}
    
    # Filter out empty target lists
    active_map = {proc: urls for proc, urls in process_map.items() if urls}
    
    if not active_map:
        logger.info("No URLs to validate.")
        return True

    logger.info(f"Validating traffic for processes: {list(active_map.keys())}")
    
    # Structure: pending[process_name][url] = found_boolean
    pending = {proc: {url: False for url in urls} for proc, urls in active_map.items()}
    
    log_buffer = ""
    validator = get_validator()
    
    for i in range(5):
        new_logs = validator.read_new_logs()
        if new_logs:
            log_buffer += new_logs
        
        all_passed = True
        for proc, urls in active_map.items():
            for url in urls:
                if not pending[proc][url]:
                    if check_tunneling_in_text(proc, url, log_buffer):
                        pending[proc][url] = True
                        logger.info(f"URL: {url} ({proc}) -> PASS")
                    else:
                        all_passed = False
        
        if all_passed:
            return True
        
        if i < 4:
            if smart_sleep(2, stop_event):
                return False

    success = True
    for proc, urls in active_map.items():
        for url in urls:
            if not pending[proc][url]:
                logger.error(f"URL: {url} ({proc}) -> FAIL !!!!!!")
                success = False
    
    return success
