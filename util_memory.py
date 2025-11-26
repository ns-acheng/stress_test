import ctypes
from ctypes import wintypes

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

    # Retrieve the first process
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


def get_proc_memory_usage(proc_name: str) -> int:
    pid = get_pid_by_name(proc_name)
    if pid == 0:
        return 0
    return get_process_memory_usage(pid)


def test_sys_mem():
    usage_rate = get_system_memory_usage()
    print(f"System Memory Usage: {usage_rate:.2%}")

def test_proc_mem(proc_name: str):
    mem_bytes = get_proc_memory_usage(proc_name)
    if mem_bytes > 0:
        mem_mb = mem_bytes / (1024 * 1024)
        print(f"Process '{proc_name}' Memory Usage: {mem_mb:.2f} MB")
    else:
        print(f"Process '{proc_name}' not found or access denied.")

if __name__ == "__main__":
    test_sys_mem()
    test_proc_mem("explorer.exe")
