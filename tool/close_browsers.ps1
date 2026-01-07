$browsers = @("msedge", "chrome", "firefox")

Get-Process -Name $browsers -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | ForEach-Object { 
    $_.CloseMainWindow() | Out-Null 
}
