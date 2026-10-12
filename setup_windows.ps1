# HTML APK Studio 0.4 - configuración no invasiva de Gradle 8.9
# Descarga exclusivamente desde services.gradle.org y verifica SHA256 publicado.
param([switch]$InstallGradle)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host 'HTML APK STUDIO - DIAGNOSTICO WINDOWS' -ForegroundColor Cyan
foreach ($tool in @('python','java','gradle')) {
  $cmd = Get-Command $tool -ErrorAction SilentlyContinue
  Write-Host "$tool : $(if ($cmd) {$cmd.Source} else {'NO ENCONTRADO'})"
}
$Sdk = if ($env:ANDROID_HOME) {$env:ANDROID_HOME} elseif ($env:ANDROID_SDK_ROOT) {$env:ANDROID_SDK_ROOT} else {Join-Path $env:LOCALAPPDATA 'Android\Sdk'}
Write-Host "Android SDK: $Sdk"
Write-Host "API 35: $(Test-Path (Join-Path $Sdk 'platforms\android-35\android.jar'))"
Write-Host "Build Tools: $(Test-Path (Join-Path $Sdk 'build-tools'))"
if (-not $InstallGradle) {
  Write-Host 'Para instalar Gradle 8.9 sin cambiar PATH del sistema, ejecuta:' -ForegroundColor Yellow
  Write-Host '  powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -InstallGradle'
  Write-Host 'Instala JDK 17 y Android SDK API 35 / Build Tools desde Android Studio si faltan.'
  exit 0
}
$dest = Join-Path $Root 'tools\gradle-8.9'
if (Test-Path (Join-Path $dest 'bin\gradle.bat')) {
  Write-Host 'Gradle 8.9 ya esta instalado.' -ForegroundColor Green
  exit 0
}
$base = 'https://services.gradle.org/distributions'
$zip = Join-Path $env:TEMP 'gradle-8.9-bin.zip'
$checksumFile = Join-Path $env:TEMP 'gradle-8.9-bin.zip.sha256'
Write-Host 'Descargando Gradle oficial y su SHA256...'
Invoke-WebRequest "$base/gradle-8.9-bin.zip" -OutFile $zip
Invoke-WebRequest "$base/gradle-8.9-bin.zip.sha256" -OutFile $checksumFile
$expected = ((Get-Content $checksumFile -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
$actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($expected -notmatch '^[a-f0-9]{64}$' -or $actual -ne $expected) {throw 'SHA256 de Gradle no coincide. No se instala.'}
$tools = Join-Path $Root 'tools'
New-Item -ItemType Directory -Path $tools -Force | Out-Null
Expand-Archive -Path $zip -DestinationPath $tools -Force
if (-not (Test-Path (Join-Path $dest 'bin\gradle.bat'))) {throw 'No se encontro gradle.bat despues de extraer'}
Write-Host 'Gradle 8.9 instalado y verificado.' -ForegroundColor Green
Write-Host 'No se modifico el PATH del sistema.'
