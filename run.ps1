param(
    [string]$Config = 'configs/default.json',
    [string]$Output = ('experiments/run_' + (Get-Date -Format 'yyyyMMdd_HHmmss')),
    [ValidateSet('2D', '3D')][string]$PositionMode,
    [double]$HeightM,
    [switch]$NoIQ,
    [switch]$Test
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $localPython) { $pythonExe = $localPython }
elseif (Test-Path -LiteralPath $bundledPython) { $pythonExe = $bundledPython }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonExe = (Get-Command python).Source }
else { throw 'Install Python 3.10+ and numpy first.' }
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
$env:PYTHONIOENCODING = 'utf-8'
$tempDir = Join-Path $PSScriptRoot 'experiments\temp'
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$env:TEMP = $tempDir
$env:TMP = $tempDir
if ($Test) { & $pythonExe -m unittest discover -s tests -v }
else {
    $simArgs = @('simulate.py','--config',$Config,'--output',$Output)
    if ($NoIQ) { $simArgs += '--no-iq' }
    if ($PositionMode) { $simArgs += @('--position-mode', $PositionMode.ToLowerInvariant()) }
    if ($PSBoundParameters.ContainsKey('HeightM')) {
        $simArgs += @('--height-m', $HeightM.ToString([Globalization.CultureInfo]::InvariantCulture))
    }
    & $pythonExe @simArgs
}
if ($LASTEXITCODE -ne 0) { throw "Python command failed with code $LASTEXITCODE" }
