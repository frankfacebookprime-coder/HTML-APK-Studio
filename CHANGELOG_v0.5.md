# HTML APK Studio v0.5 — endurecimiento previo a Windows

- Valida que un ZIP no contenga conflictos archivo/carpeta, antes de extraer.
- Rechaza HTML individuales que sean enlaces simbólicos, demasiado grandes o que coincidan con su destino.
- Añade tres pruebas de regresión.
- Conserva la interfaz, CLI, Android WebView y Gradle de v0.4.

## Estado real
No se ha compilado ningún APK ni probado en un dispositivo Android en este entorno. Para la primera prueba en Windows, ejecutar `PRUEBA_RAPIDA.cmd`, después `python cli.py doctor`, y finalmente `python cli.py build examples\demo --name "Prueba Studio" --package com.misapps.pruebatest` una vez instaladas las dependencias. Verificar la instalación en el teléfono.
