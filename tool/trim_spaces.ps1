$toolDir = $PSScriptRoot
$rootDir = Split-Path -Parent $toolDir

Write-Host "Trimming trailing spaces from Python files in: $rootDir" -ForegroundColor Cyan

$files = Get-ChildItem -Path $rootDir -Filter "*.py" -Recurse

foreach ($file in $files) {
    $filePath = $file.FullName
    Write-Host "Processing: $filePath" -ForegroundColor Gray

    $script = "import sys; path = sys.argv[1]; " +
              "lines = open(path, 'r', encoding='utf-8').readlines(); " +
              "open(path, 'w', encoding='utf-8').write(" +
              "''.join([line.rstrip() + '\n' for line in lines]))"

    python -c $script $filePath
}

Write-Host "Done." -ForegroundColor Green
