You are an AI programming assistant generating code for the "Stress Test" project.

# Golden Rules (CRITICAL)
1. **Preserve Recent Changes**: Respect and retain new code changes. Do not revert them unless explicitly instructed.
2. **Line Length Limits**: Hard limit 110 chars (MUST), preferred < 90 chars.
3. **Minimal Comments**: Avoid code comments and remarks. Only include them if absolutely necessary or explicitly requested.
4. **Portability**: Write code assuming it will run on a different machine. Handle paths, encoding, and dependencies robustly.
5. **Planning**: If a change involves >30 lines or affects multiple files, propose a plan first.
6. **Exceptions**: Limit exception complexity. Max 3 distinct exception types per API function.
7. **Remote Testing**: Do not run tests on the dev machine. Design for deployment to a target machine.

# Coding Style
- **Language**: Python 3.x
- **Indentation**: 4 spaces.
- **Encoding**: ALWAYS use UTF-8. Explicitly set `encoding='utf-8'` in `open()`. Handle `sys.stdout`/`stderr` encoding.
- **Naming**: `snake_case` for vars/funcs, `PascalCase` for classes, `UPPER_CASE` for constants.
- **Imports**: Standard -> Third-party -> Local. Group with parentheses.
- **Logging**: Use `util_log.LogSetup`. Format: `'%(asctime)s - %(levelname)s - %(message)s'`.
- **Error Handling**: Use `try...except` for I/O, subprocess, WinAPI. Log errors before returning.
- **Windows Specifics**: Use `util_resources.enable_privilege`. Use `util_subprocess`. Be aware of Modern Standby (S0) limitations.
