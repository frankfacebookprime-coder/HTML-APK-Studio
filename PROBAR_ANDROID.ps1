# Ejecuta SOLO si autorizas instalar el APK en tu propio Android por ADB.
param(
  [Parameter(Mandatory=$true)][string]$Apk,
  [Parameter(Mandatory=$true)][string]$Package
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Apk)) { throw "No existe el APK: $Apk" }
$Sdk = if ($env:ANDROID_HOME) {$env:ANDROID_HOME} elseif ($env:ANDROID_SDK_ROOT) {$env:ANDROID_SDK_ROOT} else {Join-Path $env:LOCALAPPDATA 'Android\Sdk'}
$cmd = Get-Command adb -ErrorAction SilentlyContinue
$adb = if ($cmd) {$cmd.Source} else {Join-Path $Sdk 'platform-tools\adb.exe'}
if (-not (Test-Path $adb)) {throw 'Falta adb. Instala Android SDK Platform-Tools desde Android Studio.'}
Write-Host 'Conecta un Android propio por USB, activa depuración USB y autoriza el equipo.' -ForegroundColor Cyan
$devices = @(& $adb devices | Select-String "`tdevice$")
if ($LASTEXITCODE -ne 0 -or $devices.Count -ne 1) {throw 'Se requiere exactamente un Android conectado y autorizado por ADB.'}
Write-Host "Instalando: $Apk" -ForegroundColor Yellow
& $adb install -r $Apk
if ($LASTEXITCODE -ne 0) {throw 'ADB no pudo instalar el APK.'}
Write-Host "Abriendo paquete: $Package" -ForegroundColor Yellow
& $adb shell monkey -p $Package -c android.intent.category.LAUNCHER 1
if ($LASTEXITCODE -ne 0) {throw 'ADB no pudo solicitar el inicio.'}
Start-Sleep -Seconds 3
& $adb shell pidof $Package
Write-Host 'Verifica visualmente en el telefono que se vea el HTML y funcione el boton.' -ForegroundColor Cyan
Write-Host 'La instalacion y solicitud de apertura no prueban por si solas todas las funciones.'
