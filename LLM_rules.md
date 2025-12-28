# LLM Generation Rules for Stress Test Project

This document outlines the coding standards, style guidelines, and best practices for generating code in this project.

**CRITICAL INSTRUCTION**: Follow the **Golden Rules** below under all conditions. If any other rule or instruction conflicts with them, the Golden Rules take precedence. Point out any conflicts if they arise.

## Golden Rules

1. **Preserve Recent Changes**: Respect and retain new code changes. Do not revert them unless explicitly instructed.
2. **Line Length Limits**: 
   - **Hard Limit**: 110 characters (MUST).
   - **Preferred**: < 90 characters.
3. **Minimal Comments**: Avoid code comments and remarks. Only include them if absolutely necessary or explicitly requested.
4. **Portability**: Write code assuming it will run on a different machine. Handle paths, encoding, and dependencies robustly.
5. **Planning for Large Changes**: If a change involves >30 lines or affects multiple files, **propose a plan first** before modifying any code.
6. **Simplified Exception Handling**: Limit exception complexity. Do not handle more than three distinct exception types within a single API function.
7. **Remote Testing Focus**: Do not attempt to run tests on the development machine. Always design methods and scripts to be deployed and tested on a separate target machine.


## 1. General Coding Style

- **Language**: Python 3.x
- **Indentation**: 4 spaces (no tabs).
- **Encoding**: ALWAYS use UTF-8.
  - Explicitly set `encoding='utf-8'` when opening files: `open(path, 'r', encoding='utf-8')`.
  - Ensure `sys.stdout` and `sys.stderr` are handled for UTF-8 output in console scripts.

## 2. Naming Conventions

- **Variables & Functions**: `snake_case` (e.g., `enter_s0_and_wake`, `log_resource_usage`).
- **Classes**: `PascalCase` (e.g., `StressTest`, `LogSetup`).
- **Constants**: `UPPER_CASE` (e.g., `TINY_SEC`, `WM_SYSCOMMAND`).
- **File Names**: `snake_case` (e.g., `util_power.py`, `stress_test.py`).
- **Windows API**: Keep original casing for Win32 API function names when using `ctypes` (e.g., `CreateWaitableTimerW`).

## 3. Imports

- **Order**:
  1. Standard Library (e.g., `os`, `sys`, `logging`, `ctypes`).
  2. Third-Party Libraries (e.g., `pywin32` if used).
  3. Local Application Imports (e.g., `from util_log import LogSetup`).
- **Grouping**: Group imports from the same module using parentheses for multi-line imports.

## 4. Logging

- Use the standard `logging` module.
- **Setup**: Use `util_log.LogSetup` for main scripts to ensure consistent log folder structure (`log/YYYYMMDD-HHMMSS/`).
- **Logger Instance**: `logger = logging.getLogger()` at the module level or inside classes.
- **Format**: `'%(asctime)s - %(levelname)s - %(message)s'`.
- **Levels**: Use `logger.info()` for general flow, `logger.error()` for failures, `logger.debug()` for detailed traces.

## 5. Error Handling

- Use `try...except` blocks for:
  - File I/O operations.
  - External command executions (`subprocess`).
  - Windows API calls.
- Log errors with `logger.error(f"Message: {e}")` before returning or raising.
- For critical setup failures, log to `sys.stderr` and use `sys.exit(1)`.

## 6. Windows Specifics

- **Privileges**: Use `util_resources.enable_privilege` to acquire necessary rights (e.g., `SeDebugPrivilege`).
- **Subprocesses**: Use `util_subprocess` helpers or `subprocess.run` with `capture_output=True` and `text=True`.
- **Services**: Use `win32serviceutil` or `sc.exe` via subprocess for service management.
- **Modern Standby**: Be aware of S0 vs S3 differences. Desktop apps are suspended in S0.

## 7. File Structure

- **Utilities**: Place reusable logic in `util_*.py` files.
- **Configuration**: Load configs from `data/` directory.
- **Tools**: External scripts (PS1, BAT) go in `tool/`.
- **Logs**: Output logs to `log/` directory.

## 8. Documentation

- Include docstrings for modules, classes, and complex functions.
- Use clear, descriptive comments for non-obvious logic (especially `ctypes` usage).

## 9. Example Snippet

```python
import os
import logging
from util_log import LogSetup

logger = logging.getLogger()

def process_data(file_path: str):
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = f.read()
        logger.info(f"Read {len(data)} bytes.")
        return True
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return False
```
