# HTML APK Studio Professional v0.5

**Estado: prototipo funcional de escritorio + generador de proyectos Android.** Se han probado importación, editor/GUI en entorno virtual, creación de proyecto Gradle, validaciones y pruebas unitarias. **No se ha compilado ni instalado un APK real en Android** porque este entorno no tiene Android SDK ni Gradle. No hay garantías para todos los HTML ni para apps web complejas.

Convierte un HTML, ZIP o carpeta web con `index.html` en un proyecto Android que muestra la web dentro de WebView y, con las dependencias instaladas, intenta generar un APK Android real. Pensado para **uso personal en Windows 10/11**.

## Novedades frente a v0.3

- **Interfaz futurista** oscura con cinco secciones: Convertir, Editor, Proyectos, Sistema y Registro.
- **Editor HTML** incorporado con Ctrl+S; guarda una copia de trabajo sin alterar los archivos originales.
- **Vista previa** servida por HTTP local en `127.0.0.1` para abrirla en el navegador predeterminado de Windows. No es un emulador Android.
- **Biblioteca persistente** de proyectos, configuraciones, versiones e historial. Datos en `%LOCALAPPDATA%\HTMLAPKStudio` en Windows (o `HTMLAPK_STUDIO_HOME` si se configura).
- **AndroidX WebViewAssetLoader** para recursos HTML/CSS/JS/JSON servidos bajo un origen HTTPS virtual; sin permisos de acceso a archivos locales. Soporta rutas relativas y absolutas desde la raíz del proyecto, sujeto a pruebas Android.
- **Importación endurecida**: protección ZIP traversal, enlaces simbólicos, nombres reservados Windows, rutas duplicadas, bombas de compresión y límites de tamaño.
- **Firma debug/release**: release utiliza un `.jks` del usuario, alias y contraseñas solo en memoria/variables de entorno. El número de versión aumenta tras una compilación exitosa desde la interfaz.
- **Comprobación estructural de APK** y verificación adicional con `apksigner` cuando esté disponible. La verificación estructural no sustituye la instalación.
- **CLI** para automatización con Harness: `doctor`, `validate`, `prepare`, `build`, `projects`, `demo`.
- **Preparación Windows** con PowerShell para descargar Gradle 8.9 desde fuente oficial, verificando SHA256.
- **Ejemplo de prueba** sin Internet con botón, contador y almacenamiento local.

## Iniciar en Windows

1. Extrae el ZIP completo, sin mezclarlo con versiones anteriores.
2. Instala **Python 3.10+** con Tkinter. Opcional: `python -m pip install Pillow` para generar íconos de varias densidades; sin Pillow también admite PNG en `drawable-nodpi`.
3. Ejecuta `INICIAR_STUDIO.cmd` o abre PowerShell en la carpeta y escribe `python studio.py`.
4. Importa `examples\demo` para la primera prueba, usa **Vista previa**, **Validar**, luego **Generar APK** cuando estén las dependencias.

Los proyectos e historial se guardan en `%LOCALAPPDATA%\HTMLAPKStudio`; los APK se colocan en `%LOCALAPPDATA%\HTMLAPKStudio\outputs`.

## Preparar compilación Android

Se necesita:

- **JDK 17** (recomendado) y Java en PATH. AGP 8.7.3 requiere JDK 17 como mínimo.
- **Android SDK API 35**, **Android SDK Build Tools** y licencias aceptadas, instalados desde Android Studio o `sdkmanager`.
- **Gradle 8.9**, compatible con Android Gradle Plugin 8.7.3. El proyecto incluye configuración Gradle pero **no un wrapper JAR**.
- `ANDROID_HOME` configurado al SDK (o SDK detectado en `%LOCALAPPDATA%\Android\Sdk`).
- Internet en la **primera compilación** para descargar el Android Gradle Plugin y AndroidX WebKit desde repositorios oficiales.

Desde PowerShell en la carpeta extraída:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -InstallGradle
python cli.py doctor
python -m unittest discover -s tests -v
```

El script instala **solo Gradle** en `tools\gradle-8.9` cuando se indica `-InstallGradle`; no instala Java ni SDK ni cambia variables del sistema. Para el SDK usa el SDK Manager de Android Studio: instala `Android SDK Platform 35` y `Android SDK Build-Tools`. Comprueba el diagnóstico antes de compilar.

## Prueba automatizable para Harness (sin interfaz)

```powershell
python cli.py validate examples\demo
python cli.py prepare examples\demo --name "Prueba Studio" --package com.misapps.pruebatest --dest C:\Temp\HTMLAPK-Android
python cli.py build examples\demo --name "Prueba Studio" --package com.misapps.pruebatest
```

**`prepare` NO genera APK:** prepara un proyecto Android para inspección. `build` sí invoca Gradle y solo devuelve ruta de APK si Gradle termina con éxito y el archivo pasa las comprobaciones disponibles. Aun así, **la instalación y ejecución en Android siguen pendientes** hasta probar el APK en un dispositivo o emulador.

## Probar en un Android conectado

Con un APK generado, conecta **tu propio Android** por USB, habilita depuración USB y acepta el permiso en el teléfono. El siguiente comando instala y solicita abrir la app (requiere `adb` del SDK):

```powershell
powershell -ExecutionPolicy Bypass -File .\PROBAR_ANDROID.ps1 -Apk "C:\ruta\MiApp-debug.apk" -Package "com.misapps.pruebatest"
```

Comprueba manualmente que aparece el HTML, que el botón incrementa el contador y que el valor permanece tras cerrar y volver a abrir la app. Si no se ha ejecutado en Android, no se puede afirmar que esté probado.

## Firma y actualizaciones

**Debug:** Gradle firma con la clave debug del equipo. Sirve para uso personal/pruebas, pero no es ideal para distribuir o actualizar indefinidamente. Cambiar de PC o borrar la clave debug puede impedir actualizaciones sin desinstalar.

**Release:** crea una clave privada y conserva una copia segura fuera de la carpeta del proyecto. Ejemplo orientativo en Windows (ejecuta `keytool` del JDK):

```powershell
keytool -genkeypair -v -keystore mi-clave.jks -alias miapp -keyalg RSA -keysize 3072 -validity 10000
```

En la interfaz elige `release`, selecciona el `.jks`, escribe alias y contraseñas. Las contraseñas no se guardan en `project.json` ni se pasan como argumentos a Gradle. En CLI usa:

```powershell
$env:HTMLAPK_STORE_PASSWORD = 'tu_password'
$env:HTMLAPK_KEY_PASSWORD = 'tu_password_clave'
python cli.py build examples\demo --name "Prueba Studio" --package com.misapps.pruebatest --mode release --keystore C:\Claves\mi-clave.jks --alias miapp
Remove-Item Env:\HTMLAPK_STORE_PASSWORD, Env:\HTMLAPK_KEY_PASSWORD
```

**Importante:** para actualizar una app instalada sin perder sus datos, mantén el mismo `applicationId` y la misma clave de firma; incrementa `versionCode`. La interfaz lo incrementa automáticamente tras cada compilación exitosa.

## Qué NO incluye todavía

- Compilación Android validada en este entorno ni APK instalable entregado.
- Emulador Android, vista previa WebView idéntica al dispositivo, depuración JS en tiempo real o recarga en vivo automática.
- Conversión de cualquier sitio web arbitrario o proyecto que requiera Node/Vite/React sin generar primero su carpeta `dist`/`build`.
- Permisos avanzados de cámara, micrófono, notificaciones, GPS, descargas y selector de archivos nativos.
- Creación de AAB para Google Play, firma rotativa, soporte de plugins Cordova/Capacitor, service workers garantizados.
- Instalador `.exe` firmado para Windows ni instalador de dependencias completamente automático.

## Seguridad y privacidad

Importa **solo HTML y ZIP de confianza**: la vista previa ejecuta JavaScript en tu navegador. La app no necesita API ni cuentas, no sube el código a un servidor. La vista previa se sirve únicamente en `127.0.0.1`. Los recursos remotos de HTML pueden hacer solicitudes externas si la app tiene Internet. El WebView Android no expone un `addJavascriptInterface`.

## Estructura

```text
studio.py                  Interfaz futurista (Tkinter)
studio_core.py             Importación, biblioteca, generación, compilación
cli.py                     Interfaz de línea de comandos para Harness
android-template/          Plantilla Android/Gradle con WebViewAssetLoader
examples/demo/index.html   App de prueba interactiva
setup_windows.ps1          Diagnóstico + instalador opt-in de Gradle 8.9
INICIAR_STUDIO.cmd         Iniciar GUI
PRUEBA_RAPIDA.cmd          Pruebas unitarias + preparar proyecto Android
PROBAR_ANDROID.ps1         Instalación y apertura ADB con autorización del usuario
tests/test_studio.py       Pruebas automatizadas
```

## Fuentes técnicas oficiales

- Android Gradle Plugin 8.7.3 / Gradle 8.9 / JDK 17: https://developer.android.com/build/releases/agp-8-7-0-release-notes
- Carga segura de HTML local: https://developer.android.com/develop/ui/views/layout/webapps/load-local-content
- AndroidX WebViewAssetLoader: https://developer.android.com/reference/androidx/webkit/WebViewAssetLoader
- Gradle distribuciones oficiales: https://services.gradle.org/distributions/


Consulta `CHANGELOG_v0.5.md` para los cambios y límites de esta versión.
