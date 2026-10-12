# Informe de pruebas — v0.4

**Fecha:** 12 de octubre de 2026 (UTC). **Entorno de pruebas:** Linux, Python 3.13.5, OpenJDK 21, Xvfb. **No se dispone de Android SDK, Gradle ni dispositivo Android en este entorno.**

| Prueba | Resultado | Qué demuestra |
|---|---|---|
| `python -m compileall` | OK | Sintaxis Python de GUI, CLI y motor. |
| `python -m unittest discover -s tests -v` | **28/28 OK** | Importación, seguridad ZIP, validación, proyectos persistentes, generación de plantilla, íconos, CLI y simulación del orquestador. |
| `python cli.py validate examples/demo` | OK | HTML demo aceptado, sin advertencias. |
| `python cli.py prepare ...` | OK | Se genera un árbol Android con Manifest XML parseable, Gradle, Java y assets. **No APK.** |
| GUI Xvfb | OK | Abre y cierra, muestra las 5 pestañas. |
| GUI integración | OK | Importa carpeta, edita y guarda HTML, sirve vista previa en localhost. |
| `python cli.py doctor` | OK | Detecta Java 21; confirma Gradle/SDK faltantes. |
| Prueba con Gradle simulado | OK | Prueba que Python invoca un proceso y maneja un archivo de salida. El ZIP falso **NO** es un APK instalable. |
| Compilación real `assembleDebug` | **NO REALIZADA** | Falta Gradle y Android SDK. |
| Verificación firma con `apksigner` | **NO REALIZADA** | Falta Android Build Tools. |
| Instalación y ejecución Android | **NO REALIZADA** | Falta APK real y Android conectado. |
| Ejecución nativa Windows/PowerShell | **NO REALIZADA** | Este entorno es Linux; se entregan scripts para probar en Windows. |

## Criterio para declarar éxito final

Se debe ejecutar `assembleDebug` sin errores con Gradle 8.9 y SDK 35, verificar APK con `apksigner`, instalar en Android y comprobar el botón y `localStorage` de `examples/demo`. Hasta entonces, el proyecto es una **base de compilación preparada**, no un convertidor de APK verificado de extremo a extremo.
