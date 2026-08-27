param(
    [Parameter(Mandatory = $false)]
    [string]$Version = "0.1.0",
    [Parameter(Mandatory = $false)]
    [string]$OutputDir = "artifacts",
    [Parameter(Mandatory = $false)]
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactDir = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDir))
$versionParts = @($Version.Split(".") | ForEach-Object { [int]$_ })
while ($versionParts.Count -lt 4) { $versionParts += 0 }
$fileVersion = ($versionParts[0..3] -join ", ")
$dotVersion = ($versionParts[0..3] -join ".")
$versionFile = Join-Path $repoRoot "build\windows-version-info.txt"
$pythonCandidates = @(
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
    (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$python = $pythonCandidates | Select-Object -First 1
if (-not $python) {
    throw "Python was not found. Create .venv or add Python to PATH."
}
$appVersion = (& $python (Join-Path $repoRoot "scripts\manage_version.py") current).Trim()
if ($LASTEXITCODE -ne 0 -or $Version -ne $appVersion) {
    throw "Build version '$Version' does not match APP_VERSION '$appVersion'."
}

New-Item -ItemType Directory -Path (Split-Path $versionFile) -Force | Out-Null
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null

$versionResource = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($fileVersion),
    prodvers=($fileVersion),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'kimNarr'),
         StringStruct('FileDescription', 'AI subscription usage HUD'),
         StringStruct('FileVersion', '$dotVersion'),
         StringStruct('InternalName', 'SynapCap'),
         StringStruct('OriginalFilename', 'SynapCap.exe'),
         StringStruct('ProductName', 'SynapCap'),
         StringStruct('ProductVersion', '$Version')]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
[System.IO.File]::WriteAllText($versionFile, $versionResource, [System.Text.UTF8Encoding]::new($false))

Push-Location $repoRoot
try {
    & $python "scripts\generate_icons.py"
    if ($LASTEXITCODE -ne 0) { throw "Icon generation failed." }

    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --onedir `
        --name SynapCap `
        --icon "assets\synapcap.ico" `
        --add-data "assets\synapcap-logo-source.png;assets" `
        --version-file $versionFile `
        main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

    if ($SkipInstaller) {
        Write-Output "Created Windows application bundle at dist\SynapCap"
        return
    }

    $isccCandidates = @(
        (Get-Command iscc.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    $iscc = $isccCandidates | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 compiler (ISCC.exe) was not found."
    }

    $sourceDir = Join-Path $repoRoot "dist\SynapCap"
    & $iscc `
        "/DMyAppVersion=$Version" `
        "/DSourceDir=$sourceDir" `
        "/DOutputDir=$artifactDir" `
        "packaging\windows\SynapCap.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed." }
}
finally {
    Pop-Location
}
