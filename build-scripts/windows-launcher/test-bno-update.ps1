<#
.SYNOPSIS
    End-to-end test of bno-update.ps1 against a local mock install and mock release zips.

.DESCRIPTION
    Builds a fake v0.1.0 install that holds user data in every folder the game uses on Windows,
    builds a fake v0.2.0 release zip, and runs the real updater in a child process with -Shell
    (powershell.exe for Windows PowerShell 5.1, pwsh for PowerShell 7). Checks that damaged
    downloads, checksum mismatches, failures half way and an interrupted update all leave the
    install exactly as it was, and that a good update replaces the game files, removes files the
    old release shipped and the new one dropped, and keeps every user file. No network access.
#>
[CmdletBinding()]
param(
    [string]$Shell = ''
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

if (-not $Shell) {
    if ($PSVersionTable.PSEdition -eq 'Desktop' -or $IsWindows) { $Shell = 'powershell.exe' } else { $Shell = 'pwsh' }
}
$Updater = Join-Path $PSScriptRoot 'bno-update.ps1'
$tempDir = [System.IO.Path]::GetTempPath()
if ($env:RUNNER_TEMP) { $tempDir = $env:RUNNER_TEMP }
$Root = Join-Path $tempDir ('bno-update-test-' + [guid]::NewGuid().ToString('N'))
$script:Failures = 0
$script:Completed = $false

function Write-File([string]$Path, [string]$Text) {
    [void][System.IO.Directory]::CreateDirectory((Split-Path -Parent $Path))
    [System.IO.File]::WriteAllText($Path, $Text)
}

function Assert-True([bool]$Condition, [string]$Message) {
    if ($Condition) {
        Write-Host "  ok   $Message"
    } else {
        Write-Host "  FAIL $Message"
        $script:Failures++
    }
}

function Get-TreeSnapshot([string]$Dir) {
    $prefix = $Dir.TrimEnd('\', '/').Length + 1
    $lines = foreach ($f in @(Get-ChildItem -LiteralPath $Dir -Recurse -Force -File)) {
        $rel = $f.FullName.Substring($prefix).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        "$rel $hash"
    }
    return (@($lines) | Sort-Object) -join "`n"
}

function Invoke-Updater([string]$Install, [string[]]$Arguments) {
    $all = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $Updater,
        '-InstallDir', $Install) + $Arguments
    # Windows PowerShell 5.1 turns redirected native stderr into errors; keep them as text.
    $ErrorActionPreference = 'Continue'
    $output = & $Shell @all 2>&1 | Out-String
    $code = $LASTEXITCODE
    Write-Host ($output.TrimEnd() -replace '(?m)^', '       | ')
    return [pscustomobject]@{ Code = $code; Output = $output }
}

# The user files every update must keep, by the folders path_info.cpp uses on Windows.
$UserFiles = [ordered]@{
    'save/Test World/#UGxheWVy.sav' = 'player save'
    'save/Test World/worldoptions.json' = '{"world":1}'
    'config/options.json' = '{"opt":1}'
    'config/keybindings.json' = '{"keys":1}'
    'memorial/Test World/player.txt' = 'memorial'
    'graveyard/Test World/old.sav' = 'graveyard'
    'templates/hero.template' = 'template'
    'font/myfont.ttf' = 'user font'
    'mods/MyTopMod/modinfo.json' = 'user mod in mods'
    'data/mods/MyDataMod/modinfo.json' = 'user mod in data/mods'
    'data/sound/MySoundpack/soundpack.txt' = 'user soundpack in data/sound'
    'gfx/MyTiles/tile_config.json' = 'user tileset'
    'sound/MyOtherPack/soundpack.txt' = 'user soundpack in sound'
}

function Build-MockPackage([string]$Dir, [string]$Version, [hashtable]$Files) {
    foreach ($k in $Files.Keys) { Write-File (Join-Path $Dir $k) $Files[$k] }
    Write-File (Join-Path $Dir 'VERSION.txt') "Bright Nights Overhaul $Version`r`nbuild type: test`r`n"
    foreach ($name in @('bno-update.ps1', 'Launch Bright Nights.bat', 'Update Bright Nights.bat', 'README-FIRST.txt')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $Dir $name)
    }
    $r = & $Shell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $Updater -WriteManifest $Dir
    if ($LASTEXITCODE -ne 0) { throw "Writing the manifest failed: $r" }
}

$OldFiles = @{
    'cataclysm-bn-tiles.exe' = 'old exe'
    'old-only.dll' = 'dropped in v0.2.0'
    'data/json/common.json' = 'old common'
    'data/json/old-only.json' = 'stale json'
    'data/mods/bno_old_mod/modinfo.json' = 'fork mod dropped in v0.2.0'
    'data/mods/bno_kept_mod/modinfo.json' = 'fork mod v1'
    'gfx/ShippedTiles/tile_config.json' = 'tiles v1'
    'mods/put-your-third-party-mods-here.txt' = 'placeholder v1'
}
$NewFiles = @{
    'cataclysm-bn-tiles.exe' = 'new exe'
    'data/json/common.json' = 'new common'
    'data/json/new-only.json' = 'added json'
    'data/mods/bno_kept_mod/modinfo.json' = 'fork mod v2'
    'data/mods/bno_new_mod/modinfo.json' = 'fork mod added'
    'gfx/ShippedTiles/tile_config.json' = 'tiles v2'
    'mods/put-your-third-party-mods-here.txt' = 'placeholder v2'
}

function Initialize-MockInstall([string]$Name) {
    $dir = Join-Path $Root $Name
    Build-MockPackage $dir 'v0.1.0' $OldFiles
    foreach ($k in $UserFiles.Keys) { Write-File (Join-Path $dir $k) $UserFiles[$k] }
    Write-File (Join-Path $dir '.bno-update.lock') ''
    return $dir
}

try {
    Write-Host "Updater test with $Shell in $Root"

    # Mock release: a v0.2.0 package zipped under one top-level folder, as the workflow ships it.
    $pkgParent = Join-Path $Root 'pkg'
    Build-MockPackage (Join-Path $pkgParent 'BrightNightsOverhaul') 'v0.2.0' $NewFiles
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = Join-Path $Root 'BrightNightsOverhaul-windows-x64.zip'
    [System.IO.Compression.ZipFile]::CreateFromDirectory($pkgParent, $zip, [System.IO.Compression.CompressionLevel]::Fastest, $false)
    $sha = Join-Path $Root 'good.sha256'
    Write-File $sha ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() + '  BrightNightsOverhaul-windows-x64.zip')
    $badSha = Join-Path $Root 'bad.sha256'
    Write-File $badSha (('0' * 64) + '  BrightNightsOverhaul-windows-x64.zip')
    $corrupt = Join-Path $Root 'corrupt.zip'
    $bytes = [System.IO.File]::ReadAllBytes($zip)
    [System.IO.File]::WriteAllBytes($corrupt, [byte[]]$bytes[0..([int]($bytes.Length / 3))])
    $common = @('-ZipPath', $zip, '-ZipVersion', 'v0.2.0', '-Sha256Path', $sha, '-Yes')

    $cases = @(
        @{ Name = 'corrupt zip'; Args = @('-ZipPath', $corrupt, '-ZipVersion', 'v0.2.0', '-Yes'); Code = 1 },
        @{ Name = 'checksum mismatch'; Args = @('-ZipPath', $zip, '-ZipVersion', 'v0.2.0', '-Sha256Path', $badSha, '-Yes'); Code = 1 },
        @{ Name = 'version mismatch'; Args = @('-ZipPath', $zip, '-ZipVersion', 'v0.3.0', '-Yes'); Code = 1 },
        @{ Name = 'failure half way'; Args = ($common + @('-SimulateFailureAfter', '6')); Code = 1 }
    )
    foreach ($case in $cases) {
        Write-Host "Case: $($case.Name) leaves the install unchanged"
        $dir = Initialize-MockInstall ($case.Name -replace ' ', '-')
        $before = Get-TreeSnapshot $dir
        $r = Invoke-Updater $dir $case.Args
        Assert-True ($r.Code -eq $case.Code) "exit code $($r.Code) is $($case.Code)"
        Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'every file is as before'
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $dir '.bno-update'))) 'no work folder left'
    }

    Write-Host 'Case: unsafe old manifests cannot escape the install or touch saves'
    foreach ($entry in @('../outside.txt', '/rooted.txt', 'C:/absolute.txt', 'save', 'data/../save', 'data/json/old-only.json', 'mods/CON.txt', 'gfx/name.')) {
        $dir = Initialize-MockInstall ('manifest-' + [guid]::NewGuid().ToString('N'))
        Add-Content -LiteralPath (Join-Path $dir 'bno-files.txt') -Value $entry
        $before = Get-TreeSnapshot $dir
        $r = Invoke-Updater $dir $common
        Assert-True ($r.Code -eq 1) "unsafe manifest '$entry' rejected"
        Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'unsafe manifest changes nothing'
    }

    Write-Host 'Case: unsafe archives are rejected before installation'
    foreach ($entry in @('../outside.txt', '/rooted.txt', 'C:/absolute.txt', 'BrightNightsOverhaul/data/../save/x', 'BrightNightsOverhaul/gfx/CON.txt', 'BrightNightsOverhaul/gfx/name.', 'BrightNightsOverhaul\evil.txt', 'BrightNightsOverhaul/VERSION.txt')) {
        $unsafe = Join-Path $Root ('unsafe-' + [guid]::NewGuid().ToString('N') + '.zip')
        Copy-Item -LiteralPath $zip -Destination $unsafe
        $archive = [System.IO.Compression.ZipFile]::Open($unsafe, [System.IO.Compression.ZipArchiveMode]::Update)
        try {
            [void]$archive.CreateEntry($entry)
        } finally { $archive.Dispose() }
        $dir = Initialize-MockInstall ('archive-' + [guid]::NewGuid().ToString('N'))
        $before = Get-TreeSnapshot $dir
        $r = Invoke-Updater $dir @('-ZipPath', $unsafe, '-ZipVersion', 'v0.2.0', '-Yes')
        Assert-True ($r.Code -eq 1) "unsafe archive '$entry' rejected"
        Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'unsafe archive changes nothing'
    }

    Write-Host 'Case: an archive symlink is rejected'
    $unsafe = Join-Path $Root 'symlink.zip'
    Copy-Item -LiteralPath $zip -Destination $unsafe
    $archive = [System.IO.Compression.ZipFile]::Open($unsafe, [System.IO.Compression.ZipArchiveMode]::Update)
    try {
        $link = $archive.CreateEntry('BrightNightsOverhaul/link')
        $link.ExternalAttributes = -1577123840 # Unix S_IFLNK | 0777 in upper 16 bits.
    } finally { $archive.Dispose() }
    $dir = Initialize-MockInstall 'symlink'
    $before = Get-TreeSnapshot $dir
    $r = Invoke-Updater $dir @('-ZipPath', $unsafe, '-ZipVersion', 'v0.2.0', '-Yes')
    Assert-True ($r.Code -eq 1) 'symlink archive rejected'
    Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'symlink archive changes nothing'

    Write-Host 'Case: an unsafe recovery journal is retained without touching user files'
    $dir = Initialize-MockInstall 'unsafe-journal'
    Write-File (Join-Path $dir '.bno-update/journal.txt') "BEGIN|update`nPLACE|../outside.txt"
    $before = Get-TreeSnapshot $dir
    $r = Invoke-Updater $dir $common
    Assert-True ($r.Code -eq 2) 'unsafe journal blocks launch'
    Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'unsafe journal is retained and changes nothing'

    Write-Host 'Case: a second updater cannot acquire the install lock'
    $dir = Initialize-MockInstall 'locked'
    $before = Get-TreeSnapshot $dir
    $lock = [System.IO.File]::Open((Join-Path $dir '.bno-update.lock'),
        [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    try {
        $r = Invoke-Updater $dir $common
        Assert-True ($r.Code -eq 2) 'concurrent update blocks launch'
    } finally { $lock.Dispose() }
    Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'concurrent update changes nothing'

    if ($env:OS -eq 'Windows_NT') {
        Write-Host 'Case: a running game prevents update and interrupted recovery'
        $dir = Initialize-MockInstall 'running'
        Copy-Item -LiteralPath $env:ComSpec -Destination (Join-Path $dir 'cataclysm-bn-tiles.exe') -Force
        Write-File (Join-Path $dir '.bno-update/journal.txt') "BEGIN|update`nPLACE|old-only.dll"
        $before = Get-TreeSnapshot $dir
        $game = Start-Process -FilePath (Join-Path $dir 'cataclysm-bn-tiles.exe') `
            -ArgumentList '/c ping -n 30 127.0.0.1 >nul' -PassThru -WindowStyle Hidden
        try {
            $r = Invoke-Updater $dir $common
            Assert-True ($r.Code -eq 2 -and $r.Output -match 'game is running') 'running game blocks recovery and launch'
            Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'running install and journal are untouched'
        } finally { Stop-Process -Id $game.Id -Force -ErrorAction SilentlyContinue }
    }

    Write-Host 'Case: an update stopped half way is rolled back on the next run'
    $dir = Initialize-MockInstall 'interrupted'
    $before = Get-TreeSnapshot $dir
    $r = Invoke-Updater $dir ($common + @('-SimulateCrashAfter', '5'))
    Assert-True ($r.Code -eq 3) "the simulated crash exits with 3 (got $($r.Code))"
    Assert-True (Test-Path -LiteralPath (Join-Path $dir '.bno-update/journal.txt')) 'the journal survives the crash'
    $r = Invoke-Updater $dir @('-ZipPath', $zip, '-ZipVersion', 'v0.1.0', '-Yes')
    Assert-True ($r.Code -eq 0) "the next run exits with 0 (got $($r.Code))"
    Assert-True ($r.Output -match 'did not finish') 'the next run reports the interrupted update'
    Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'every file is as before'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $dir '.bno-update'))) 'no work folder left'

    Write-Host 'Case: replaying rollback retains the original backup'
    $dir = Initialize-MockInstall 'rollback-replay'
    $before = Get-TreeSnapshot $dir
    # Model power loss after a rollback already restored this file, but before cleanup.
    Write-File (Join-Path $dir '.bno-update/backup/old-only.dll') 'dropped in v0.2.0'
    Write-File (Join-Path $dir '.bno-update/journal.txt') "BEGIN|update`nBACKUP|old-only.dll`nPLACE|old-only.dll"
    $r = Invoke-Updater $dir @('-ZipPath', $zip, '-ZipVersion', 'v0.1.0', '-Yes')
    Assert-True ($r.Code -eq 0) 'rollback can be replayed'
    Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'replayed rollback keeps every original file'

    Write-Host 'Case: a good update installs v0.2.0 and keeps user data'
    $dir = Initialize-MockInstall 'good'
    $r = Invoke-Updater $dir $common
    Assert-True ($r.Code -eq 0) "exit code $($r.Code) is 0"
    $version = [System.IO.File]::ReadAllText((Join-Path $dir 'VERSION.txt'))
    Assert-True ($version -match 'v0\.2\.0') 'VERSION.txt says v0.2.0'
    foreach ($k in $NewFiles.Keys) {
        $p = Join-Path $dir $k
        Assert-True ((Test-Path -LiteralPath $p) -and [System.IO.File]::ReadAllText($p) -eq $NewFiles[$k]) "$k is the new copy"
    }
    foreach ($k in @('old-only.dll', 'data/json/old-only.json', 'data/mods/bno_old_mod')) {
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $dir $k))) "$k from the old release is gone"
    }
    foreach ($k in $UserFiles.Keys) {
        $p = Join-Path $dir $k
        Assert-True ((Test-Path -LiteralPath $p) -and [System.IO.File]::ReadAllText($p) -eq $UserFiles[$k]) "user file $k is kept"
    }
    $manifest = [System.IO.File]::ReadAllText((Join-Path $dir 'bno-files.txt'))
    Assert-True ($manifest -match 'data/mods/bno_new_mod' -and $manifest -notmatch 'MyDataMod') 'bno-files.txt lists the new release only'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $dir '.bno-update'))) 'no work folder left'

    Write-Host 'Case: the same version again is a no-op'
    $before = Get-TreeSnapshot $dir
    $r = Invoke-Updater $dir @('-Mode', 'Check', '-ZipPath', $zip, '-ZipVersion', 'v0.2.0', '-Yes')
    Assert-True ($r.Code -eq 0 -and $r.Output -match 'newest version') 'reports the newest version'
    Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'every file is as before'

    Write-Host 'Case: Launch mode stays quiet and fast when GitHub cannot be reached'
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-Updater $dir @('-Mode', 'Launch', '-ApiUrl', 'http://127.0.0.1:9/releases/latest', '-TimeoutSec', '3')
    $watch.Stop()
    Assert-True ($r.Code -eq 0) "exit code $($r.Code) is 0"
    Assert-True ($r.Output.Trim() -eq '') 'prints nothing'
    Assert-True ($watch.Elapsed.TotalSeconds -lt 30) "returns in $([int]$watch.Elapsed.TotalSeconds) s"

    Write-Host 'Case: download, checksum and install through a mock GitHub API'
    # python before python3: on Windows runners python3 can be a Microsoft Store stub.
    $python = Get-Command python, python3 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $python) {
        Assert-True (-not $env:CI) 'python for the mock API server (required on CI)'
    } else {
        $www = Join-Path $Root 'www'
        [void][System.IO.Directory]::CreateDirectory($www)
        Copy-Item -LiteralPath $zip -Destination (Join-Path $www 'BrightNightsOverhaul-windows-x64.zip')
        Copy-Item -LiteralPath $sha -Destination (Join-Path $www 'BrightNightsOverhaul-windows-x64.zip.sha256')
        $port = Get-Random -Minimum 20000 -Maximum 40000
        $base = "http://127.0.0.1:$port"
        $release = @{
            tag_name = 'v0.2.0'
            name = 'Bright Nights Overhaul v0.2.0'
            html_url = "$base/release"
            assets = @(
                @{ name = 'BrightNightsOverhaul-windows-x64.zip'; size = (Get-Item -LiteralPath $zip).Length; browser_download_url = "$base/BrightNightsOverhaul-windows-x64.zip" },
                @{ name = 'BrightNightsOverhaul-windows-x64.zip.sha256'; size = 100; browser_download_url = "$base/BrightNightsOverhaul-windows-x64.zip.sha256" }
            )
        }
        Write-File (Join-Path $www 'latest.json') ($release | ConvertTo-Json -Depth 4)
        $server = Start-Process -FilePath $python.Source -PassThru `
            -RedirectStandardOutput (Join-Path $Root 'server.out') -RedirectStandardError (Join-Path $Root 'server.err') `
            -ArgumentList @('-m', 'http.server', "$port", '--bind', '127.0.0.1', '--directory', "`"$www`"")
        try {
            $ready = $false
            for ($i = 0; $i -lt 50 -and -not $ready; $i++) {
                try {
                    [void](Invoke-WebRequest -Uri "$base/latest.json" -UseBasicParsing -TimeoutSec 2)
                    $ready = $true
                } catch {
                    Start-Sleep -Milliseconds 200
                }
            }
            Assert-True $ready 'the mock API server answers'
            $dir = Initialize-MockInstall 'http'
            $r = Invoke-Updater $dir @('-ApiUrl', "$base/latest.json", '-Yes')
            Assert-True ($r.Code -eq 0) "exit code $($r.Code) is 0"
            Assert-True ($r.Output -match [regex]::Escape("$base/release")) 'shows the release link'
            $version = [System.IO.File]::ReadAllText((Join-Path $dir 'VERSION.txt'))
            Assert-True ($version -match 'v0\.2\.0') 'VERSION.txt says v0.2.0'
            $save = Join-Path $dir 'save/Test World/#UGxheWVy.sav'
            Assert-True ((Test-Path -LiteralPath $save) -and [System.IO.File]::ReadAllText($save) -eq 'player save') 'the save is kept'

            Write-Host 'Case: a network release without its checksum is refused'
            $release.assets = @($release.assets[0])
            Write-File (Join-Path $www 'latest.json') ($release | ConvertTo-Json -Depth 4)
            $dir = Initialize-MockInstall 'missing-checksum'
            $before = Get-TreeSnapshot $dir
            $r = Invoke-Updater $dir @('-ApiUrl', "$base/latest.json", '-Yes')
            Assert-True ($r.Code -eq 1 -and $r.Output -match 'no SHA-256') 'missing checksum fails closed'
            Assert-True ((Get-TreeSnapshot $dir) -eq $before) 'missing checksum changes nothing'
        } finally {
            Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
        }
    }
    $script:Completed = $true
} finally {
    if ($script:Completed -and $script:Failures -eq 0) {
        if (Test-Path -LiteralPath $Root) { Remove-Item -LiteralPath $Root -Recurse -Force }
    } else {
        Write-Host "Failure evidence retained in $Root"
    }
}

if ($script:Failures -gt 0) {
    Write-Host "$script:Failures check(s) failed."
    exit 1
}
Write-Host 'All updater checks passed.'
exit 0
