$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot\frontend"
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($npm) {
    if (-not (Test-Path node_modules/react-router-dom)) {
        & $npm.Source ci
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    & $npm.Source run dev
} else {
    # Portable Node installed for this checkout by the local verification tools.
    $nodeDir = "$PSScriptRoot\backend\.verify-env\Lib\site-packages\nodejs_wheel"
    if (-not (Test-Path "$nodeDir\node.exe")) { throw 'Install Node.js 22.12+ with npm, then reopen PowerShell.' }
    $env:Path = "$nodeDir;$env:Path"
    $cli = "$nodeDir\lib\node_modules\npm\bin\npm-cli.js"
    if (-not (Test-Path node_modules/react-router-dom)) {
        & "$nodeDir\node.exe" $cli ci
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    & "$nodeDir\node.exe" $cli run dev
}
