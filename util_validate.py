import os
import re
import logging
import threading
import codecs

logger = logging.getLogger(__name__)

class NsClientLogValidator:
    def __init__(self, log_path=None):
        if log_path:
            self.log_path = log_path
        else:
            prog_data = os.environ.get('ProgramData', 'C:\\ProgramData')
            self.log_path = os.path.join(
                prog_data, 'netskope', 'stagent', 'logs', 'nsdebuglog.log'
            )
        
        self.rotated_log_path = self.log_path.replace('.log', '.1.log')
        self.lock = threading.Lock()
        self.last_pos = 0

    def update_pos_to_end(self):
        with self.lock:
            if os.path.exists(self.log_path):
                try:
                    self.last_pos = os.path.getsize(self.log_path)
                except OSError:
                    self.last_pos = 0

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

_validator = None
_validator_lock = threading.Lock()

def get_validator():
    global _validator
    with _validator_lock:
        if _validator is None:
            _validator = NsClientLogValidator()
    return _validator

def check_nsclient_log(pattern):
    validator = get_validator()
    return validator.check_log(pattern, is_regex=False)

def check_nsclient_log_regex(pattern, flags=0):
    validator = get_validator()
    return validator.check_log(pattern, flags=flags, is_regex=True)
