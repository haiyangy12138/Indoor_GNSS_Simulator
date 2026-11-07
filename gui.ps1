# Launch the local Python/Tk parameter application.
param([switch]$Console)
$ErrorActionPreference = 'Stop'
try {
    Set-Location -LiteralPath $PSScriptRoot
    $localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $localPython) { $pythonExe = $localPython }
    elseif (Test-Path -LiteralPath $bundledPython) { $pythonExe = $bundledPython }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonExe = (Get-Command python).Source }
    else { throw '需要 Python 3.10+、NumPy 和 Tkinter。' }
    $env:PYTHONIOENCODING = 'utf-8'
    & $pythonExe -c 'import numpy, tkinter'
    if ($LASTEXITCODE -ne 0) { throw '当前 Python 缺少 NumPy 或 Tkinter。' }
    $entry = Join-Path $PSScriptRoot 'app.py'
    if ($Console) { & $pythonExe $entry; exit $LASTEXITCODE }
    $pythonWindowless = Join-Path (Split-Path $pythonExe) 'pythonw.exe'
    if (-not (Test-Path -LiteralPath $pythonWindowless)) { $pythonWindowless = $pythonExe }
    $logDir = Join-Path $PSScriptRoot 'experiments\temp\gui'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $tag = [guid]::NewGuid().ToString('N')
    $errLog = Join-Path $logDir ($tag + '.startup.log')
    $appProcess = Start-Process -FilePath $pythonWindowless -ArgumentList @('"' + $entry + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Normal -RedirectStandardError $errLog -PassThru
    if ($appProcess.WaitForExit(1500) -and $appProcess.ExitCode -ne 0) { throw ('启动失败。日志：' + $errLog) }
} catch {
    $shell = New-Object -ComObject WScript.Shell
    [void]$shell.Popup($_.Exception.Message, 0, '室内定位仿真', 16)
    exit 1
}
