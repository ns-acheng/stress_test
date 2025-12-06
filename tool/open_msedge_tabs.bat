@echo off
setlocal enabledelayedexpansion

if "%~1"=="" (
    echo No URLs provided.
    echo Usage: %~nx0 url1 url2 ... url10
    goto :end
)
start "" msedge --new-window about:blank

set /a count=0

:loop
if "%~1"=="" goto :finished

if !count! GEQ 10 goto :finished

start "" msedge "%~1"

timeout /t 1 /nobreak >nul
set /a count+=1
shift

goto :loop

:finished

:end
endlocal
exit