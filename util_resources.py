import ctypes
from ctypes import wintypes
import time
import os
from datetime import datetime

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SE_DEBUG_NAME = "SeDebugPrivilege"
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002

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

class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.LONG),
    ]

class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Luid", LUID),
        ("Attributes", wintypes.DWORD),
    ]

class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),
    ]

def enable_privilege(privilege_name):
    k32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32
    
    hToken = wintypes.HANDLE()
    
    if not k32.OpenProcessToken(
        k32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(hToken)
    ):
        return ctypes.get_last_error()

    luid = LUID()
    if not advapi32.LookupPrivilegeValueW(
        None, privilege_name, ctypes.byref(luid)
    ):
        err = ctypes.get_last_error()
        k32.CloseHandle(hToken)
        return err

    tp = TOKEN_PRIVILEGES()
    tp.PrivilegeCount = 1
    tp.Privileges[0].Luid = luid
    tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

    if not advapi32.AdjustTokenPrivileges(
        hToken, False, ctypes.byref(tp), 0, None, None
    ):
        err = ctypes.get_last_error()
        k32.CloseHandle(hToken)
        return err
    
    err = ctypes.get_last_error()
    k32.CloseHandle(hToken)
    return err

def _filetime_to_int(ft):
    return (ft.dwHighDateTime << 32) + ft.dwLowDateTime

def _get_num_processors():
    sys_info = SYSTEM_INFO()
    ctypes.windll.kernel32.GetSystemInfo(ctypes.byref(sys_info))
    return sys_info.dwNumberOfProcessors

def get_system_memory_usage():
    mem_status = MEMORYSTATUSEX()
    mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))
    return mem_status.dwMemoryLoad / 100.0

def get_pid_by_name(process_name: str) -> int:
    k32 = ctypes.windll.kernel32
    hSnapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    
    if hSnapshot == INVALID_HANDLE_VALUE:
        return 0

    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

    if not k32.Process32FirstW(hSnapshot, ctypes.byref(entry)):
        k32.CloseHandle(hSnapshot)
        return 0

    target_pid = 0
    try:
        while True:
            if entry.szExeFile.lower() == process_name.lower():
                target_pid = entry.th32ProcessID
                break

            if not k32.Process32NextW(hSnapshot, ctypes.byref(entry)):
                break
    finally:
        k32.CloseHandle(hSnapshot)
        
    return target_pid

def get_process_memory_usage(pid: int) -> int:
    if pid == 0: 
        return 0
    
    k32 = ctypes.windll.kernel32
    process_handle = k32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
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
            return counters.PrivateUsage
        else:
            return 0
    finally:
        k32.CloseHandle(process_handle)

def get_process_handle_count(pid: int) -> int:
    if pid == 0:
        return 0
    
    k32 = ctypes.windll.kernel32
    process_handle = k32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid
    )
    
    if not process_handle:
        return 0
        
    try:
        count = wintypes.DWORD()
        success = k32.GetProcessHandleCount(
            process_handle, ctypes.byref(count)
        )
        return count.value if success else 0
    finally:
        k32.CloseHandle(process_handle)

def get_process_cpu_usage(pid: int, interval: float = 0.5) -> float:
    if pid == 0:
        return 0.0

    k32 = ctypes.windll.kernel32
    process_handle = k32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid
    )

    if not process_handle:
        return 0.0

    try:
        creation = FILETIME()
        exit_time = FILETIME()
        k_start = FILETIME()
        u_start = FILETIME()
        sys_start = FILETIME()
        
        k32.GetProcessTimes(
            process_handle, 
            ctypes.byref(creation), 
            ctypes.byref(exit_time), 
            ctypes.byref(k_start), 
            ctypes.byref(u_start)
        )
        k32.GetSystemTimeAsFileTime(ctypes.byref(sys_start))
        
        time.sleep(interval)
        
        k_end = FILETIME()
        u_end = FILETIME()
        sys_end = FILETIME()
        
        k32.GetProcessTimes(
            process_handle, 
            ctypes.byref(creation), 
            ctypes.byref(exit_time), 
            ctypes.byref(k_end), 
            ctypes.byref(u_end)
        )
        k32.GetSystemTimeAsFileTime(ctypes.byref(sys_end))
        
        p_k_delta = _filetime_to_int(k_end) - _filetime_to_int(k_start)
        p_u_delta = _filetime_to_int(u_end) - _filetime_to_int(u_start)
        sys_delta = _filetime_to_int(sys_end) - _filetime_to_int(sys_start)
        
        if sys_delta == 0:
            return 0.0
            
        num_procs = _get_num_processors()
        cpu_pct = (
            ((p_k_delta + p_u_delta) / sys_delta) * 100.0 / num_procs
        )
        
        return max(0.0, cpu_pct)

    finally:
        k32.CloseHandle(process_handle)

def log_resource_usage(
    process_name: str,
    log_dir="log"
):
    pid = get_pid_by_name(process_name)
    if pid == 0:
        return False
        
    mem_bytes = get_process_memory_usage(pid)
    mem_kb = mem_bytes / 1024
    mem_mb = mem_bytes / (1024 * 1024)
    
    handle_count = get_process_handle_count(pid)
    cpu_percent = get_process_cpu_usage(pid, interval=0.5)
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = f"{process_name}_resources.log"
    full_path = os.path.join(log_dir, log_file)
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    
    write_header = not os.path.exists(full_path)

    log_line = (
        f"{now_str}, {cpu_percent:.0f}%, "
        f"{mem_mb:.1f}MB, {mem_kb:.0f}KB, {handle_count}\n"
    )
    
    with open(full_path, "a", encoding='utf-8') as f:
        if write_header:
            f.write("Timestamp, CPU, Memory(MB), Memory(KB), Handles\n")
        f.write(log_line)
        
    return True

if __name__ == "__main__":
    target = "stAgentSvc.exe"
    ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    try:
        while True:
            log_resource_usage(target, ts)
            time.sleep(4.5) 
    except KeyboardInterrupt:
        pass