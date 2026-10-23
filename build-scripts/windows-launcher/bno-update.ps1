<#
.SYNOPSIS
    Updates a portable Bright Nights Overhaul install from GitHub Releases.

.DESCRIPTION
    Shipped next to cataclysm-bn-tiles.exe in BrightNightsOverhaul-windows-x64.zip and run by
    "Launch Bright Nights.bat" (-Mode Launch) and "Update Bright Nights.bat" (-Mode Check).

    It reads the local VERSION.txt, asks the GitHub API for the newest release of the fork and,
    when that release is newer, offers to install it. In Launch mode any network or API problem
    is silent so the game always starts.

    The Windows build keeps everything the player owns in the game folder: main.cpp calls
    PATH_INFO::init_user_dir( "." ) unless USE_HOME_DIR or USE_XDG_DIR is set, and the Windows
    build sets neither (CMakeLists.txt: USE_HOME_DIR defaults to OFF on WIN32). path_info.cpp then
    puts save/, memorial/, graveyard/, templates/, config/, font/ (user fonts), mods/ (user mods),
    gfx/ (user tilesets, shared with the shipped gfx/) and sound/ (user soundpacks) under that
    folder. The update therefore:
      - never touches the user-data folders in $PreservedRoots;
      - merges the folders in $MergeDirs one level deep: entries the release ships replace the old
        copies, everything else in them (the player's own mods, tilesets, soundpacks) stays;
      - replaces every other shipped file or folder whole, so data/json never keeps stale files;
      - removes files an older release shipped that the new one dropped, using bno-files.txt.
    Replaced files go to .bno-update\backup and come back if anything fails. A journal lets the
    next run finish the rollback if the computer stops in the middle of an update.

    Exit codes: 0 no update needed, declined, or installed; 1 the update failed and was rolled
    back; 2 the rollback was incomplete (the old files stay in .bno-update\backup).

    The script must stay ASCII-only and Windows PowerShell 5.1 compatible.
#>
[CmdletBinding()]
param(
    # Launch: quiet when up to date or offline. Check: always report the result.
    [ValidateSet('Launch', 'Check')]
    [string]$Mode = 'Check',

    # The game folder to update. Defaults to the folder holding this script.
    [string]$InstallDir = '',

    [string]$Repository = 'Kenja-mc/Cataclysm-BN',
    [string]$AssetName = 'BrightNightsOverhaul-windows-x64.zip',
    [string]$ApiUrl = '',
    [int]$TimeoutSec = 5,

    # Install without asking.
    [switch]$Yes,

    # Write bno-files.txt for the package folder given here and exit. Used by the release workflow.
    [string]$WriteManifest = '',

    # Testing hooks: install from a local zip instead of GitHub.
    [string]$ZipPath = '',
    [string]$ZipVersion = '',
    [string]$Sha256Path = '',
    [int]$SimulateFailureAfter = -1,
    [int]$SimulateCrashAfter = -1
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# User data the game keeps in its own folder on Windows (see the description above).
$PreservedRoots = @('save', 'config', 'memorial', 'graveyard', 'templates', 'font', '.bno-update', '.bno-update.lock')
# Folders that hold both shipped content and the player's additions.
$MergeDirs = @('data', 'data/mods', 'data/sound', 'gfx', 'mods', 'sound')
$ManifestName = 'bno-files.txt'
$VersionName = 'VERSION.txt'
$GameExe = 'cataclysm-bn-tiles.exe'
$RequiredEntries = @($GameExe, 'data', 'gfx', $VersionName, $ManifestName, 'bno-update.ps1',
    'Launch Bright Nights.bat', 'Update Bright Nights.bat', 'README-FIRST.txt')

$script:MoveCount = 0

function Write-Line([string]$Text) {
    Write-Host $Text
}

function Get-SemVer([string]$Text) {
    if ($null -eq $Text) { return $null }
    $m = [regex]::Match($Text, '(?m)^(?:Bright Nights Overhaul )?v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\r?$')
    if (-not $m.Success) { return $null }
    return New-Object System.Version ([int]$m.Groups[1].Value), ([int]$m.Groups[2].Value), ([int]$m.Groups[3].Value)
}

function Format-Version($Version) {
    if ($null -eq $Version) { return 'unknown' }
    return 'v' + $Version.ToString(3)
}

function Read-VersionFile([string]$Dir) {
    $path = Join-Path $Dir $VersionName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
    return Get-SemVer ([System.IO.File]::ReadAllText($path))
}

function Join-Rel([string]$Base, [string]$Rel) {
    $path = $Base
    foreach ($part in $Rel.Split('/')) {
        if ($part) { $path = Join-Path $path $part }
    }
    return $path
}

function Join-RelName([string]$Rel, [string]$Name) {
    if ($Rel) { return $Rel + '/' + $Name }
    return $Name
}

function Test-Preserved([string]$Rel) {
    $root = $Rel.Split('/')[0]
    foreach ($p in $PreservedRoots) {
        if ($root -ieq $p) { return $true }
    }
    return $false
}

function Test-MergeDir([string]$Rel) {
    foreach ($m in $MergeDirs) {
        if ($Rel -ieq $m) { return $true }
    }
    return $false
}

# Apply Windows path rules even when packaging or testing on Linux.
function Assert-SafePath([string]$Rel) {
    if (-not $Rel -or $Rel -match '[\\<>:"|?*\x00-\x1f]') { throw "Unsafe path: $Rel" }
    foreach ($part in $Rel.Split('/')) {
        if (-not $part -or $part -eq '.' -or $part -eq '..' -or $part -match '[. ]$' -or
            $part -match '^(?i:CON|CONIN\$|CONOUT\$|PRN|AUX|NUL|COM[0-9\u00b9\u00b2\u00b3]|LPT[0-9\u00b9\u00b2\u00b3])(?:[ .]|$)') {
            throw "Unsafe path: $Rel"
        }
    }
}

function Assert-OwnedPath([string]$Rel) {
    Assert-SafePath $Rel
    if (Test-Preserved $Rel) { throw "Manifest or journal touches user data: $Rel" }
    $parts = $Rel.Split('/')
    $parent = ''
    for ($i = 0; $i -lt $parts.Count - 1; $i++) {
        $parent = Join-RelName $parent $parts[$i]
        if (-not (Test-MergeDir $parent)) { throw "Invalid owned path: $Rel" }
    }
}

function Assert-NoReparseTree([string]$Path, [switch]$Shallow) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "Links and junctions are not supported by the updater: $Path"
    }
    if ($item.PSIsContainer -and -not $Shallow) {
        foreach ($child in @(Get-ChildItem -LiteralPath $Path -Force)) {
            Assert-NoReparseTree $child.FullName
        }
    }
}

function Assert-Journal([string[]]$Lines) {
    foreach ($line in $Lines) {
        if ($line -eq 'BEGIN|update' -or $line -eq 'COMMITTED') { continue }
        $parts = $line.Split('|')
        if ($parts.Count -ne 2 -or $parts[0] -notin @('PLACE', 'BACKUP')) {
            throw 'The recovery journal is invalid. Keep .bno-update for manual recovery.'
        }
        Assert-OwnedPath $parts[1]
    }
}

# Top-level entries plus the children of every merge folder: the paths a release owns.
function Get-PackageEntryList([string]$Root, [string]$Rel = '') {
    $result = New-Object System.Collections.Generic.List[string]
    $dir = Join-Rel $Root $Rel
    foreach ($child in @(Get-ChildItem -LiteralPath $dir -Force | Sort-Object Name)) {
        $childRel = Join-RelName $Rel $child.Name
        if (Test-Preserved $childRel) { continue }
        $result.Add($childRel)
        if ($child.PSIsContainer -and (Test-MergeDir $childRel)) {
            foreach ($inner in (Get-PackageEntryList $Root $childRel)) { $result.Add($inner) }
        }
    }
    return , $result
}

function Write-Manifest([string]$Root) {
    $entries = Get-PackageEntryList $Root
    foreach ($entry in $entries) { Assert-OwnedPath $entry }
    $entries.Add($ManifestName)
    $lines = @($entries | Sort-Object -Unique)
    [System.IO.File]::WriteAllLines((Join-Path $Root $ManifestName), [string[]]$lines)
}

function Read-Manifest([string]$Dir) {
    $path = Join-Path $Dir $ManifestName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return @() }
    $entries = @([System.IO.File]::ReadAllLines($path) | Where-Object { $_ -and -not $_.StartsWith('#') })
    foreach ($entry in $entries) { Assert-OwnedPath $entry }
    return $entries
}

function Move-Raw([string]$From, [string]$To) {
    [void][System.IO.Directory]::CreateDirectory((Split-Path -Parent $To))
    $attempt = 0
    while ($true) {
        try {
            if ([System.IO.Directory]::Exists($From)) {
                [System.IO.Directory]::Move($From, $To)
            } else {
                [System.IO.File]::Move($From, $To)
            }
            return
        } catch {
            # Antivirus scanners often hold freshly extracted files for a moment.
            $attempt++
            if ($attempt -ge 5) { throw }
            Start-Sleep -Milliseconds (400 * $attempt)
        }
    }
}

function Move-Entry([string]$From, [string]$To) {
    $script:MoveCount++
    if ($SimulateCrashAfter -ge 0 -and $script:MoveCount -gt $SimulateCrashAfter) {
        [Environment]::Exit(3)
    }
    if ($SimulateFailureAfter -ge 0 -and $script:MoveCount -gt $SimulateFailureAfter) {
        throw "Simulated failure before moving $From"
    }
    Move-Raw $From $To
}

function Test-Entry([string]$Path) {
    return [System.IO.Directory]::Exists($Path) -or [System.IO.File]::Exists($Path)
}

function Add-Journal([string]$Line) {
    [System.IO.File]::AppendAllText($script:Journal, $Line + [Environment]::NewLine)
}

function Clear-WorkDir([string]$Work) {
    if (Test-Path -LiteralPath $Work) {
        Remove-Item -LiteralPath $Work -Recurse -Force
    }
}

# Undo a journal in reverse order. Returns $true when every step succeeded.
function Undo-Journal([string]$Work) {
    $journal = Join-Path $Work 'journal.txt'
    if (-not (Test-Path -LiteralPath $journal -PathType Leaf)) { return $true }
    $lines = @([System.IO.File]::ReadAllLines($journal))
    Assert-Journal $lines
    [array]::Reverse($lines)
    $backup = Join-Path $Work 'backup'
    $discard = Join-Path $Work ('discard-' + [guid]::NewGuid().ToString('N'))
    $ok = $true
    $n = 0
    foreach ($line in $lines) {
        $parts = $line.Split('|')
        if ($parts.Count -ne 2) { continue }
        $rel = $parts[1]
        $target = Join-Rel $InstallDir $rel
        try {
            if ($parts[0] -eq 'PLACE' -and (Test-Entry $target)) {
                $n++
                Move-Raw $target (Join-Rel $discard ("$n/" + $rel))
            } elseif ($parts[0] -eq 'BACKUP') {
                $saved = Join-Rel $backup $rel
                if (Test-Entry $saved) {
                    if (Test-Entry $target) {
                        $n++
                        Move-Raw $target (Join-Rel $discard ("$n/" + $rel))
                    }
                    # Keep the backup until ALL rollback actions finish. Recovery can itself
                    # be interrupted and replayed without losing the only original copy.
                    Copy-Item -LiteralPath $saved -Destination $target -Recurse -Force
                }
            }
        } catch {
            $ok = $false
            Write-Line "Could not restore ${rel}: $($_.Exception.Message)"
        }
    }
    return $ok
}

# A journal without a COMMITTED line means an update stopped half way: put the old files back.
function Resume-Interrupted([string]$Work) {
    $journal = Join-Path $Work 'journal.txt'
    if (-not (Test-Path -LiteralPath $journal -PathType Leaf)) {
        Clear-WorkDir $Work
        return $true
    }
    $lines = @([System.IO.File]::ReadAllLines($journal))
    Assert-Journal $lines
    if ($lines -contains 'COMMITTED') {
        Clear-WorkDir $Work
        return $true
    }
    Write-Line 'An earlier update did not finish. Restoring the previous game files...'
    if (Undo-Journal $Work) {
        Clear-WorkDir $Work
        Write-Line 'The previous version is back in place.'
        return $true
    }
    Write-Line "Some files could not be restored. Your old files are in $Work\backup."
    return $false
}

function Move-ToBackup([string]$Rel) {
    Add-Journal "BACKUP|$Rel"
    Move-Entry (Join-Rel $InstallDir $Rel) (Join-Rel $script:Backup $Rel)
}

function Install-Folder([string]$Stage, [string]$Rel) {
    $children = @(Get-ChildItem -LiteralPath (Join-Rel $Stage $Rel) -Force | Sort-Object Name)
    # VERSION.txt goes last so an unfinished update never claims the new version.
    $ordered = @($children | Where-Object { -not ((-not $Rel) -and $_.Name -ieq $VersionName) }) +
        @($children | Where-Object { (-not $Rel) -and $_.Name -ieq $VersionName })
    foreach ($child in $ordered) {
        $childRel = Join-RelName $Rel $child.Name
        if (Test-Preserved $childRel) { continue }
        $target = Join-Rel $InstallDir $childRel
        if ($child.PSIsContainer -and (Test-MergeDir $childRel) -and [System.IO.Directory]::Exists($target)) {
            Install-Folder $Stage $childRel
            continue
        }
        if (Test-Entry $target) { Move-ToBackup $childRel }
        Add-Journal "PLACE|$childRel"
        Move-Entry $child.FullName $target
    }
}

function Find-PackageRoot([string]$Stage) {
    if (Test-Path -LiteralPath (Join-Path $Stage $GameExe) -PathType Leaf) { return $Stage }
    $dirs = @(Get-ChildItem -LiteralPath $Stage -Directory -Force)
    if ($dirs.Count -eq 1 -and (Test-Path -LiteralPath (Join-Path $dirs[0].FullName $GameExe) -PathType Leaf)) {
        return $dirs[0].FullName
    }
    throw 'The download does not contain the game.'
}

function Get-ExpectedHash([string]$Path) {
    $text = [System.IO.File]::ReadAllText($Path)
    $m = [regex]::Match($text, '\A([0-9a-fA-F]{64})(?:[ \t]+\*?([^\r\n]+))?\r?\n?\z')
    if (-not $m.Success -or ($m.Groups[2].Success -and $m.Groups[2].Value -cne $AssetName)) {
        throw 'The checksum file is not readable or names a different archive.'
    }
    return $m.Groups[1].Value.ToLowerInvariant()
}

function Test-GameRunning {
    $exe = Join-Path $InstallDir $GameExe
    $procs = @(Get-Process -Name 'cataclysm-bn-tiles' -ErrorAction SilentlyContinue)
    foreach ($p in $procs) {
        $path = $null
        try { $path = $p.Path } catch { $path = $null }
        if (-not $path -or ($path -ieq $exe)) { return $true }
    }
    return $false
}

function Get-LatestRelease {
    $uri = $ApiUrl
    if (-not $uri) { $uri = "https://api.github.com/repos/$Repository/releases/latest" }
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    } catch {
        Write-Verbose 'TLS 1.2 could not be enabled explicitly.'
    }
    return Invoke-RestMethod -Uri $uri -UseBasicParsing -TimeoutSec $TimeoutSec -UserAgent 'bno-update' `
        -Headers @{ Accept = 'application/vnd.github+json' }
}

function Get-Asset($Release, [string]$Name) {
    if (-not ($Release.PSObject.Properties.Name -contains 'assets')) { return $null }
    foreach ($a in @($Release.assets)) {
        if ($a.name -eq $Name) { return $a }
    }
    return $null
}

function Get-ReleaseField($Release, [string]$Name) {
    if ($Release.PSObject.Properties.Name -contains $Name) { return [string]$Release.$Name }
    return ''
}

function Save-Download([string]$Url, [string]$OutFile) {
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -UserAgent 'bno-update'
}

# Download (or copy), verify, extract and install one release. Throws when it fails before any
# game file moved; once files move it returns 'ok', 'rolledback' or 'incomplete'.
function Install-Release([string]$Work, $Wanted, $Release) {
    $download = Join-Path $Work 'download'
    $stage = Join-Path $Work 'stage'
    $script:Backup = Join-Path $Work 'backup'
    $script:Journal = Join-Path $Work 'journal.txt'
    [void][System.IO.Directory]::CreateDirectory($download)
    [void][System.IO.Directory]::CreateDirectory($stage)
    $zip = Join-Path $download $AssetName
    $shaFile = ''

    if ($ZipPath) {
        Copy-Item -LiteralPath $ZipPath -Destination $zip
        if ($Sha256Path) { $shaFile = $Sha256Path }
        $expectedSize = -1
    } else {
        $asset = Get-Asset $Release $AssetName
        if ($null -eq $asset) { throw "The release has no $AssetName." }
        $expectedSize = [int64]$asset.size
        Write-Line ('Downloading {0:N0} MB...' -f [math]::Ceiling($expectedSize / 1MB))
        Save-Download $asset.browser_download_url $zip
        $shaAsset = Get-Asset $Release ($AssetName + '.sha256')
        if ($null -eq $shaAsset) { throw 'The release has no SHA-256 checksum.' }
        $shaFile = Join-Path $download ($AssetName + '.sha256')
        Save-Download $shaAsset.browser_download_url $shaFile
    }

    $size = (Get-Item -LiteralPath $zip).Length
    if ($size -le 0) { throw 'The download is empty.' }
    if ($expectedSize -gt 0 -and $size -ne $expectedSize) {
        throw "The download is incomplete ($size of $expectedSize bytes)."
    }
    if ($shaFile) {
        $expected = Get-ExpectedHash $shaFile
        $actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($expected -ne $actual) { throw 'The download is damaged (checksum mismatch).' }
    }

    Write-Line 'Unpacking...'
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zip)
    try {
        $seen = @{}
        foreach ($entry in $archive.Entries) {
            $rel = $entry.FullName.TrimEnd('/')
            Assert-SafePath $rel
            if ($seen.ContainsKey($rel)) { throw "Duplicate archive path: $rel" }
            $seen[$rel] = $true
            $kind = ($entry.ExternalAttributes -shr 16) -band 0xF000
            if ($kind -eq 0xA000 -or ($entry.ExternalAttributes -band 0x400)) {
                throw "Archive contains a link: $rel"
            }
        }
    } finally {
        $archive.Dispose()
    }
    try {
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $stage)
    } catch {
        throw "The download is damaged: $($_.Exception.Message)"
    }
    $root = Find-PackageRoot $stage
    foreach ($entry in $RequiredEntries) {
        $type = 'Leaf'
        if ($entry -in @('data', 'gfx')) { $type = 'Container' }
        if (-not (Test-Path -LiteralPath (Join-Path $root $entry) -PathType $type)) {
            throw "The download is missing $entry or it has the wrong type."
        }
    }
    $packaged = Read-VersionFile $root
    if ($null -eq $packaged -or $packaged -ne $Wanted) {
        throw "The download is $(Format-Version $packaged), expected $(Format-Version $Wanted)."
    }

    Write-Line 'Installing (your saves and settings are not touched)...'
    $oldManifest = Read-Manifest $InstallDir
    $newEntries = Get-PackageEntryList $root
    foreach ($entry in $newEntries) { Assert-OwnedPath $entry }
    $newManifest = Read-Manifest $root
    if (@(Compare-Object @($newEntries | Sort-Object -Unique) @($newManifest | Sort-Object -Unique)).Count -ne 0) {
        throw 'The package ownership manifest does not match its files.'
    }
    # Reject a package that tries to replace a shared container with a file.
    foreach ($merge in $MergeDirs) {
        $path = Join-Rel $root $merge
        if ((Test-Entry $path) -and -not [System.IO.Directory]::Exists($path)) {
            throw "The shared folder $merge is not a directory."
        }
    }
    if (Test-GameRunning) { throw 'Close the running game before updating.' }
    Add-Journal 'BEGIN|update'
    try {
        Install-Folder $root ''
        # Remove what the old release shipped and the new one no longer does.
        $keep = @{}
        foreach ($e in $newEntries) { $keep[$e.ToLowerInvariant()] = $true }
        foreach ($old in $oldManifest) {
            if ($keep.ContainsKey($old.ToLowerInvariant())) { continue }
            if ($old -ieq $ManifestName -or (Test-Preserved $old) -or (Test-MergeDir $old)) { continue }
            if (Test-Entry (Join-Rel $InstallDir $old)) { Move-ToBackup $old }
        }
        Add-Journal 'COMMITTED'
    } catch {
        $reason = $_.Exception.Message
        Write-Line "The update failed: $reason"
        Write-Line 'Putting the previous version back...'
        if (Undo-Journal $Work) {
            Clear-WorkDir $Work
            Write-Line 'Your game is unchanged.'
            return 'rolledback'
        }
        Write-Line "Some files could not be restored. Your old files are in $Work\backup."
        return 'incomplete'
    }
    Clear-WorkDir $Work
    return 'ok'
}

function Wait-Enter([string]$Prompt) {
    if ($Yes) { return }
    try { [void](Read-Host $Prompt) } catch { Write-Verbose 'No console input.' }
}

function Invoke-Update {
    if ($WriteManifest) {
        Write-Manifest (Resolve-Path -LiteralPath $WriteManifest).ProviderPath
        return 0
    }

    if (-not $InstallDir) { $script:InstallDir = $PSScriptRoot }
    $script:InstallDir = (Resolve-Path -LiteralPath $InstallDir).ProviderPath
    if ($ZipPath) { $script:ZipPath = (Resolve-Path -LiteralPath $ZipPath).ProviderPath }
    if ($Sha256Path) { $script:Sha256Path = (Resolve-Path -LiteralPath $Sha256Path).ProviderPath }
    Assert-NoReparseTree $InstallDir -Shallow
    Assert-NoReparseTree (Join-Path $InstallDir '.bno-update.lock') -Shallow
    if (Test-GameRunning) {
        Write-Line 'The game is running. Close it before updating or recovering an interrupted update.'
        return 2
    }
    # A separate lock survives work-folder cleanup and excludes a second updater.
    try {
        $script:UpdateLock = [System.IO.File]::Open((Join-Path $InstallDir '.bno-update.lock'),
            [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    } catch {
        Write-Line 'Another updater is running. Wait for it to finish.'
        return 2
    }
    $work = Join-Path $InstallDir '.bno-update'
    if (Test-Path -LiteralPath $work) {
        Assert-NoReparseTree $InstallDir
        if (-not (Resume-Interrupted $work)) { return 2 }
    }

    $local = Read-VersionFile $InstallDir
    $release = $null
    if ($ZipPath) {
        $wanted = Get-SemVer $ZipVersion
        if ($null -eq $wanted) { throw '-ZipVersion must look like v1.2.3.' }
    } else {
        try {
            $release = Get-LatestRelease
            $wanted = Get-SemVer (Get-ReleaseField $release 'tag_name')
        } catch {
            if ($Mode -eq 'Check') {
                Write-Line "Could not reach GitHub to check for updates: $($_.Exception.Message)"
            }
            return 0
        }
        if ($null -eq $wanted) {
            if ($Mode -eq 'Check') { Write-Line 'The newest release has no readable version.' }
            return 0
        }
        if ($null -eq (Get-Asset $release $AssetName)) {
            if ($Mode -eq 'Check') { Write-Line "The newest release has no $AssetName yet." }
            return 0
        }
    }

    if ($null -ne $local -and $wanted -le $local) {
        if ($Mode -eq 'Check') { Write-Line "You have the newest version ($(Format-Version $local))." }
        return 0
    }

    Write-Line ''
    Write-Line "Bright Nights Overhaul $(Format-Version $wanted) is available (you have $(Format-Version $local))."
    if ($null -ne $release) {
        $title = Get-ReleaseField $release 'name'
        $link = Get-ReleaseField $release 'html_url'
        if ($title) { Write-Line "  $title" }
        if ($link) { Write-Line "  What changed: $link" }
    }
    if (-not $Yes) {
        $answer = ''
        try { $answer = Read-Host "Update to $(Format-Version $wanted) now? [Y/n]" } catch { $answer = 'n' }
        if ($answer -and $answer.Trim() -notmatch '^(y|yes)$') {
            Write-Line 'Skipped. Run "Update Bright Nights" any time to update.'
            return 0
        }
    }
    if (Test-GameRunning) {
        Write-Line 'The game is running. Close it, then run "Update Bright Nights".'
        Wait-Enter 'Press Enter to continue'
        return 1
    }

    $result = 'ok'
    try {
        Assert-NoReparseTree $InstallDir
        $result = Install-Release $work $wanted $release
    } catch {
        # Never discard a recovery journal after files may have moved.
        Write-Line "The update failed: $($_.Exception.Message)"
        if (Test-Path -LiteralPath (Join-Path $work 'journal.txt')) {
            Write-Line "Keep $work for recovery; the launcher will not start a possibly incomplete install."
            return 2
        }
        Clear-WorkDir $work
        Write-Line 'Your game is unchanged.'
        Wait-Enter 'Press Enter to continue'
        return 1
    }
    if ($result -ne 'ok') {
        Wait-Enter 'Press Enter to continue'
        if ($result -eq 'incomplete') { return 2 }
        return 1
    }
    Write-Line "Updated to $(Format-Version $wanted)."
    return 0
}

$code = 0
try {
    $code = Invoke-Update
} catch {
    Write-Line "Updater error: $($_.Exception.Message)"
    # A startup/recovery exception must not let the launcher start an uncertain install.
    $code = 2
} finally {
    if (Get-Variable -Name UpdateLock -Scope Script -ErrorAction SilentlyContinue) {
        if ($null -ne $script:UpdateLock) { $script:UpdateLock.Dispose() }
    }
}
exit $code
