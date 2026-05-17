<#
.SYNOPSIS
    Сборка релизной версии Personal Finance для Windows.

.DESCRIPTION
    Этапы (каждый — опциональный, выключается флагом):
      1. Создать/активировать venv, поставить зависимости
      2. Прогнать ruff + mypy + pytest (-SkipChecks чтобы пропустить)
      3. Собрать .exe через flet build windows (-SkipBuild)
      4. Подписать .exe через signtool, если задан -CertPath
      5. Собрать инсталлер через Inno Setup, если найден iscc.exe (-SkipInstaller)
      6. Подписать инсталлер тем же сертификатом

    Подпись и инсталлер опциональны: их отсутствие не валит сборку, только
    выводит предупреждение. Это позволяет одной командой получить полный
    подписанный релиз, если все инструменты установлены, и просто .exe иначе.

.PARAMETER Version
    Версия для инсталлера. По умолчанию читается из git describe.

.PARAMETER CertPath
    Путь к .pfx сертификату для подписи. Если не задан — подпись пропускается.

.PARAMETER CertPassword
    Пароль к .pfx сертификату. Безопаснее задавать через переменную
    PFM_CERT_PASSWORD; параметр командной строки виден в истории.

.PARAMETER TimestampUrl
    RFC 3161 timestamp server. По умолчанию http://timestamp.digicert.com.

.EXAMPLE
    .\scripts\build_win.ps1
    # Базовая сборка без подписи

.EXAMPLE
    .\scripts\build_win.ps1 -Version 1.0.1 -CertPath C:\certs\pfm.pfx
    # Полный релиз: проверки → .exe → подпись .exe → инсталлер → подпись инсталлера
#>
param(
  [string]$Python = "py -3.12",
  [switch]$NoVenv,
  [switch]$SkipChecks,
  [switch]$SkipBuild,
  [switch]$SkipInstaller,
  [string]$Version = "",
  [string]$CertPath = "",
  [string]$CertPassword = "",
  [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
  Write-Host ""
  Write-Host "== $Message ==" -ForegroundColor Cyan
}

function Write-Warn($Message) {
  Write-Host "[warn] $Message" -ForegroundColor Yellow
}

function Resolve-Version {
  if ($Version) { return $Version }
  try {
    $tag = (git describe --tags --abbrev=0 2>$null).Trim()
    if ($tag) { return ($tag -replace '^v', '') }
  } catch {}
  return "0.0.0-dev"
}

function Find-Signtool {
  $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  # Поиск в типовом расположении Windows SDK
  $candidates = Get-ChildItem -Path "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse `
    -Filter "signtool.exe" -ErrorAction SilentlyContinue |
    Where-Object { $_.Directory.FullName -like "*x64*" } |
    Sort-Object -Property FullName -Descending
  if ($candidates) { return $candidates[0].FullName }
  return $null
}

function Sign-Binary($SigntoolPath, $Target) {
  $pwd = $CertPassword
  if (-not $pwd) { $pwd = $env:PFM_CERT_PASSWORD }
  $args = @(
    "sign",
    "/fd", "SHA256",
    "/tr", $TimestampUrl,
    "/td", "SHA256",
    "/f", $CertPath
  )
  if ($pwd) { $args += @("/p", $pwd) }
  $args += $Target
  & $SigntoolPath @args
  if ($LASTEXITCODE -ne 0) {
    throw "signtool failed for $Target (exit $LASTEXITCODE)"
  }
}

# ── 0. Заголовок ─────────────────────────────────────────────────────────────
Write-Host "== Personal Finance (Variant 43) :: Windows release build ==" -ForegroundColor Cyan
$resolvedVersion = Resolve-Version
Write-Host "Version: $resolvedVersion"

# ── 1. Окружение и зависимости ───────────────────────────────────────────────
if (-not $NoVenv) {
  if (-not (Test-Path ".venv")) {
    Write-Step "Создаю venv"
    Invoke-Expression "$Python -m venv .venv"
  }
  .\.venv\Scripts\Activate.ps1
}
$Py = "python"

Write-Step "Зависимости (app + dev)"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r requirements/app.txt -r requirements/dev.txt

# ── 2. Проверки ──────────────────────────────────────────────────────────────
if (-not $SkipChecks) {
  Write-Step "Проверки (ruff / mypy / pytest)"
  & $Py -m ruff check .
  & $Py -m mypy
  & $Py -m pytest -q
} else {
  Write-Warn "Проверки пропущены (-SkipChecks)"
}

# ── 3. Сборка .exe ───────────────────────────────────────────────────────────
if (-not $SkipBuild) {
  Write-Step "flet build windows"
  flet build windows --project PersonalFinance
} else {
  Write-Warn "Сборка пропущена (-SkipBuild)"
}

$exe = "build\windows\PersonalFinance.exe"
if (-not (Test-Path $exe)) {
  throw "Не нашёл $exe — flet build не выполнен или провалился"
}

# ── 4. Подпись .exe ──────────────────────────────────────────────────────────
$signtool = $null
if ($CertPath) {
  if (-not (Test-Path $CertPath)) {
    throw "CertPath не существует: $CertPath"
  }
  $signtool = Find-Signtool
  if (-not $signtool) {
    Write-Warn "signtool.exe не найден (нужен Windows SDK). Пропускаю подпись."
  } else {
    Write-Step "Подпись $exe"
    Sign-Binary $signtool $exe
  }
} else {
  Write-Warn "CertPath не задан — .exe останется без подписи (SmartScreen покажет предупреждение пользователю)"
}

# ── 5. Инсталлер ─────────────────────────────────────────────────────────────
$installer = $null
if (-not $SkipInstaller) {
  $iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
  if (-not $iscc) {
    Write-Warn "iscc.exe (Inno Setup) не найден в PATH. Скачайте с https://jrsoftware.org/isinfo.php и добавьте в PATH."
    Write-Warn "Пропускаю сборку инсталлера. Голый .exe лежит в build\windows\"
  } else {
    Write-Step "Inno Setup: scripts\installer.iss"
    & $iscc.Source "/DMyAppVersion=$resolvedVersion" "scripts\installer.iss"
    if ($LASTEXITCODE -ne 0) {
      throw "Inno Setup упал (exit $LASTEXITCODE)"
    }
    $installer = "build\installer\PersonalFinance-Setup-$resolvedVersion.exe"
    if (-not (Test-Path $installer)) {
      throw "Не нашёл итоговый $installer"
    }
  }
} else {
  Write-Warn "Инсталлер пропущен (-SkipInstaller)"
}

# ── 6. Подпись инсталлера ────────────────────────────────────────────────────
if ($installer -and $signtool) {
  Write-Step "Подпись $installer"
  Sign-Binary $signtool $installer
}

# ── Итоги ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "== Готово ==" -ForegroundColor Green
Write-Host "  .exe       : $exe"
if ($installer) { Write-Host "  Installer  : $installer" }
if (-not $signtool -or -not $CertPath) {
  Write-Host ""
  Write-Warn "Артефакты не подписаны. Пользователи увидят SmartScreen-предупреждение."
  Write-Warn "Получите Authenticode-сертификат и пересоберите с -CertPath."
}
