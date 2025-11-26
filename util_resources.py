import ctypes
from ctypes import wintypes
import time
import os
from datetime import datetime

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260) 
    ]

class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]

class SYSTEM_INFO(ctypes.Structure):
    _fields_ = [
        ("wProcessorArchitecture", wintypes.WORD),
        ("wReserved", wintypes.WORD),
        ("dwPageSize", wintypes.DWORD),
        ("lpMinimumApplicationAddress", ctypes.c_void_p),
        ("lpMaximumApplicationAddress", ctypes.c_void_p),
        ("dwActiveProcessorMask", ctypes.c_void_p),
        ("dwNumberOfProcessors", wintypes.DWORD),
        ("dwProcessorType", wintypes.DWORD),
        ("dwAllocationGranularity", wintypes.DWORD),
        ("wProcessorLevel", wintypes.WORD),
        ("wProcessorRevision", wintypes.WORD),
    ]

def _filetime_to_int(ft):
    return (ft.dwHighDateTime << 32) + ft.dwLowDateTime

def _get_num_processors():
    sys_info = SYSTEM_INFO()
    ctypes.windll.kernel32.GetSystemInfo(ctypes.byref(sys_info))
    return sys_info.dwNumberOfProcessors

def get_system_memory_usage():
    memory_status = MEMORYSTATUSEX()
    memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
    return memory_status.dwMemoryLoad / 100.0

def get_pid_by_name(process_name: str) -> int:
    hSnapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPPROCESS, 0
    )
    
    if hSnapshot == INVALID_HANDLE_VALUE:
        return 0

    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

    if not ctypes.windll.kernel32.Process32FirstW(hSnapshot, ctypes.byref(entry)):
        ctypes.windll.kernel32.CloseHandle(hSnapshot)
        return 0

    target_pid = 0
    while True:
        if entry.szExeFile.lower() == process_name.lower():
            target_pid = entry.th32ProcessID
            break

        if not ctypes.windll.kernel32.Process32NextW(hSnapshot, ctypes.byref(entry)):
            break

    ctypes.windll.kernel32.CloseHandle(hSnapshot)
    return target_pid

def get_process_memory_usage(pid: int) -> int:
    if pid == 0: 
        return 0
        
    process_handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
        False,
        pid
    )

    if not process_handle:
        return 0

    try:
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        
        success = ctypes.windll.psapi.GetProcessMemoryInfo(
            process_handle,
            ctypes.byref(counters),
            ctypes.sizeof(counters)
        )
        
        if success:
            return counters.WorkingSetSize
        else:
            return 0
    finally:
        ctypes.windll.kernel32.CloseHandle(process_handle)

def get_process_handle_count(pid: int) -> int:
    if pid == 0:
        return 0
        
    process_handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION,
        False,
        pid
    )
    
    if not process_handle:
        return 0
        
    try:
        count = wintypes.DWORD()
        success = ctypes.windll.kernel32.GetProcessHandleCount(
            process_handle,
            ctypes.byref(count)
        )
        return count.value if success else 0
    finally:
        ctypes.windll.kernel32.CloseHandle(process_handle)

def get_process_cpu_usage(pid: int, interval: float = 0.5) -> float:
    if pid == 0:
        return 0.0

    process_handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION,
        False,
        pid
    )

    if not process_handle:
        return 0.0

    try:
        creation, exit_time, kernel_start, user_start = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        sys_start = FILETIME()
        
        ctypes.windll.kernel32.GetProcessTimes(process_handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel_start), ctypes.byref(user_start))
        ctypes.windll.kernel32.GetSystemTimeAsFileTime(ctypes.byref(sys_start))
        
        time.sleep(interval)
        
        kernel_end, user_end = FILETIME(), FILETIME()
        sys_end = FILETIME()
        
        ctypes.windll.kernel32.GetProcessTimes(process_handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel_end), ctypes.byref(user_end))
        ctypes.windll.kernel32.GetSystemTimeAsFileTime(ctypes.byref(sys_end))
        
        proc_kernel_delta = _filetime_to_int(kernel_end) - _filetime_to_int(kernel_start)
        proc_user_delta = _filetime_to_int(user_end) - _filetime_to_int(user_start)
        sys_delta = _filetime_to_int(sys_end) - _filetime_to_int(sys_start)
        
        if sys_delta == 0:
            return 0.0
            
        num_processors = _get_num_processors()
        cpu_percent = ((proc_kernel_delta + proc_user_delta) / sys_delta) * 100.0 / num_processors
        
        return max(0.0, cpu_percent)

    finally:
        ctypes.windll.kernel32.CloseHandle(process_handle)

def log_resource_usage(process_name: str, log_dir="log", log_file="resource_monitor.csv"):
    pid = get_pid_by_name(process_name)
    if pid == 0:
        return False
        
    mem_bytes = get_process_memory_usage(pid)
    mem_mb = mem_bytes / (1024 * 1024)
    
    handle_count = get_process_handle_count(pid)
    cpu_percent = get_process_cpu_usage(pid, interval=0.5)
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    full_path = os.path.join(log_dir, log_file)
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    log_line = f"{now_str}, {cpu_percent:.0f}%, {mem_mb:.1f} MB, {handle_count}\n"
    
    with open(full_path, "a") as f:
        f.write(log_line)
        
    return True

if __name__ == "__main__":
    target = "explorer.exe"
    try:
        while True:
            log_resource_usage(target)
            time.sleep(4.5) 
    except KeyboardInterrupt:
        pass