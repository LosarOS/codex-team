# Explicit, user-launched updater; no background service and no account calls.
[CmdletBinding()]
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = [IO.Path]::GetFullPath($PSScriptRoot)
$exe = Join-Path $root 'CodexTeam.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    $installKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{A8024F47-5105-41CC-91F4-AD0786CD418F}_is1'
    $registered = (Get-ItemProperty -LiteralPath $installKey -Name InstallLocation -ErrorAction SilentlyContinue).InstallLocation
    $locations = @($registered, (Join-Path $env:LOCALAPPDATA 'Programs\CodexTeam'))
    foreach ($location in $locations) {
        if ($location -and (Test-Path -LiteralPath (Join-Path $location 'CodexTeam.exe') -PathType Leaf)) {
            $root = [IO.Path]::GetFullPath($location).TrimEnd('\')
            $exe = Join-Path $root 'CodexTeam.exe'
            break
        }
    }
}
$headers = @{ 'User-Agent' = 'Codex-Team-Updater'; Accept = 'application/vnd.github+json' }
$allowed = @('CodexTeam.exe','_internal','НАЧАЛО.txt','THIRD-PARTY-NOTICES.txt','Обновить.cmd','Update.ps1')
function Version-Key([string]$value) {
    $m = [regex]::Match($value.Trim(), '^v?(\d+)\.(\d+)\.(\d+)(?:-?rc(\d+))?$')
    if (-not $m.Success) { throw "Неподдерживаемая версия: $value" }
    $rank = if ($m.Groups[4].Success) { [int]$m.Groups[4].Value } else { 2147483647 }
    return [version]::new([int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value,$rank)
}
function Assert-Stopped {
    foreach ($process in Get-Process) {
        try { $path = $process.Path } catch { continue }
        if ($path -and ($path.Equals($exe,[StringComparison]::OrdinalIgnoreCase) -or $path.StartsWith($root + '\',[StringComparison]::OrdinalIgnoreCase))) {
            throw 'Закройте Codex Team перед обновлением. Приложение не будет завершено принудительно.'
        }
    }
}
$work = $null
$mutex = $null
$ownsMutex = $false
try {
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Сначала установите Codex Team. Приложение не найдено рядом с программой обновления или в каталоге установки.' }
    if ((Get-Item -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Обновление через ссылку на каталог запрещено.' }
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $lockId = [BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))).Replace('-','') } finally { $hasher.Dispose() }
    $mutex = New-Object Threading.Mutex($false, ('Local\CodexTeamUpdate_' + $lockId))
    try { $ownsMutex = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $ownsMutex = $true }
    if (-not $ownsMutex) { throw 'Обновление уже запущено. Дождитесь завершения первой копии.' }
    if (-not $CheckOnly) { Assert-Stopped }
    $current = Version-Key ([Diagnostics.FileVersionInfo]::GetVersionInfo($exe).ProductVersion)
    $portable = Test-Path -LiteralPath (Join-Path $root 'portable.json') -PathType Leaf
    $assetName = if ($portable) { 'CodexTeam-Portable-x64.zip' } else { 'CodexTeam-Setup-x64.exe' }
    Write-Host 'Проверяем опубликованные обновления Codex Team…'
    # CI runners share anonymous API limits. Its short-lived read token is used
    # only for this fixed API endpoint, never asset downloads or persisted files.
    $apiHeaders = $headers.Clone()
    if ($env:GITHUB_ACTIONS -eq 'true' -and $env:CODEX_TEAM_UPDATE_GITHUB_TOKEN) {
        $apiHeaders['Authorization'] = 'Bearer ' + $env:CODEX_TEAM_UPDATE_GITHUB_TOKEN
    }
    try {
        $releases = @(Invoke-RestMethod -Uri 'https://api.github.com/repos/LosarOS/codex-team/releases?per_page=100' -Headers $apiHeaders -MaximumRedirection 0 -TimeoutSec 30)
    } catch {
        $response = $_.Exception.Response
        if ($response -and ([int]$response.StatusCode -in @(403,429))) {
            throw 'GitHub отклонил проверку обновлений (HTTP 403/429). Возможно, временно исчерпан лимит запросов. Повторите позже или скачайте архив на https://github.com/LosarOS/codex-team/releases'
        }
        throw
    }
    $candidates = @()
    foreach ($release in $releases) {
        if ($release.draft) { continue }
        try { $key = Version-Key $release.tag_name } catch { continue }
        $assets = @($release.assets | Where-Object { $_.name -ceq $assetName })
        if ($assets.Count -eq 1 -and $key -gt $current) { $candidates += [pscustomobject]@{ Key=$key; Release=$release; Asset=$assets[0] } }
    }
    $chosen = $candidates | Sort-Object Key -Descending | Select-Object -First 1
    if (-not $chosen) { Write-Host 'Установлена актуальная совместимая версия.'; exit 0 }
    $asset = $chosen.Asset
    $expected = 'https://github.com/LosarOS/codex-team/releases/download/' + $chosen.Release.tag_name + '/' + $assetName
    if ($asset.browser_download_url -cne $expected -or $asset.digest -cnotmatch '^sha256:[0-9a-f]{64}$') { throw 'Нет достоверной SHA256 или адрес файла обновления не соответствует репозиторию.' }
    Write-Host ('Доступна версия ' + $chosen.Release.tag_name + '. Пользовательские данные сохраняются.')
    if ($CheckOnly) { Write-Host 'Проверка завершена; скачивание и установка не запускались.'; exit 0 }
    if ((Read-Host 'Скачать и установить? Введите ДА') -cne 'ДА') { exit 0 }
    $work = Join-Path $root ('.codex-update-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $work | Out-Null
    $download = Join-Path $work $assetName
    Invoke-WebRequest -UseBasicParsing -Uri $expected -Headers $headers -OutFile $download -TimeoutSec 600
    if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant() -cne $asset.digest.Substring(7)) { throw 'SHA256 загруженного файла не совпадает. Установка отменена.' }
    Assert-Stopped
    if (-not $portable) {
        $install = Start-Process -FilePath $download -ArgumentList ('/DIR="' + $root + '"') -Wait -PassThru
        if ($install.ExitCode -ne 0) { throw ('Установщик завершился с кодом ' + $install.ExitCode) }
        Write-Host 'Обновление установлено.'
    } else {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $stage = Join-Path $work 'stage'
        New-Item -ItemType Directory -Path $stage | Out-Null
        $zip = [IO.Compression.ZipFile]::OpenRead($download)
        try {
            $seen = @{}; $expanded = [long]0
            foreach ($entry in $zip.Entries) {
                $name = $entry.FullName.Replace('\','/')
                $parts = $name.Split('/')
                $expanded += $entry.Length
                if ($expanded -gt 4294967296) { throw 'Архив обновления превышает допустимый размер.' }
                foreach ($part in $parts) { if ($part -and ($part.EndsWith('.') -or $part.EndsWith(' ') -or $part -match '[<>"|?*]' -or $part -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)')) { throw 'Недопустимое имя файла в архиве.' } }
                if ($name.StartsWith('/') -or $name.Contains(':') -or $parts -contains '..' -or $parts -contains '.' -or $parts[0] -cne 'CodexTeam' -or $parts.Count -lt 2 -or (($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Небезопасный путь в архиве обновления.' }
                if ($parts[1] -ceq 'portable.json') { continue }
                if ($allowed -cnotcontains $parts[1]) { throw ('Неожиданный файл в архиве: ' + $name) }
                $relative = ($parts[1..($parts.Count-1)] -join '/')
                if ($seen.ContainsKey($relative)) { throw 'Повторяющийся путь в архиве.' }
                $seen[$relative] = $true
                $target = [IO.Path]::GetFullPath((Join-Path $stage $relative))
                if (-not $target.StartsWith($stage + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Путь выходит за пределы временного каталога.' }
                if ($name.EndsWith('/')) { New-Item -ItemType Directory -Force -Path $target | Out-Null } else {
                    New-Item -ItemType Directory -Force -Path ([IO.Path]::GetDirectoryName($target)) | Out-Null
                    [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$target,$false)
                }
            }
        } finally { $zip.Dispose() }
        foreach ($required in @('CodexTeam.exe','_internal','Update.ps1','Обновить.cmd')) { if (-not (Test-Path -LiteralPath (Join-Path $stage $required))) { throw ('Неполный архив: ' + $required) } }
        $next = Version-Key ([Diagnostics.FileVersionInfo]::GetVersionInfo((Join-Path $stage 'CodexTeam.exe')).ProductVersion)
        if ($next -ne $chosen.Key -or $next -le $current) { throw 'Версия приложения внутри архива не совпадает с выбранным обновлением.' }
        Assert-Stopped
        $backup = Join-Path $root ('.codex-backup-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $backup | Out-Null
        $moved = @(); $installed = @()
        try {
            foreach ($item in $allowed) {
                $old = Join-Path $root $item
                $new = Join-Path $stage $item
                if (Test-Path -LiteralPath $old) {
                    if ((Get-Item -LiteralPath $old -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Ссылка вместо файла приложения: обновление отменено.' }
                    Move-Item -LiteralPath $old -Destination (Join-Path $backup $item)
                    $moved += $item
                }
                if (Test-Path -LiteralPath $new) { Move-Item -LiteralPath $new -Destination $old; $installed += $item }
            }
        } catch {
            $failure = $_
            foreach ($item in $installed) { Move-Item -LiteralPath (Join-Path $root $item) -Destination (Join-Path $stage $item) }
            foreach ($item in $moved) { Move-Item -LiteralPath (Join-Path $backup $item) -Destination (Join-Path $root $item) }
            throw $failure
        }
        Write-Host ('Обновление установлено. Резервная копия сохранена: ' + $backup)
    }
} catch {
    Write-Host ('Обновление не выполнено: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    if ($work -and (Split-Path -Parent $work) -ceq $root -and (Split-Path -Leaf $work) -match '^\.codex-update-[0-9a-f]{32}$') {
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($ownsMutex) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
}
