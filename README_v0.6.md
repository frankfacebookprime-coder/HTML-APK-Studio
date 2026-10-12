# HTML APK Studio v0.6 — Modo sencillo (experimental)

Actualización incremental de v0.5. No reemplaza la versión funcional.

- Importar HTML/ZIP/carpeta puede iniciar compilación automática (casilla activada).
- En PROYECTOS, doble clic abre el proyecto guardado; doble clic en un registro APK abre su carpeta.
- `INICIAR_SIN_TERMINAL.vbs` intenta iniciar Python sin consola visible.
- La ejecución de Gradle en Windows solicita ocultar su consola.
- Busca Gradle tanto en v0.6 como en ubicaciones habituales de v0.5.

## Importante

Probado: 31 pruebas unitarias en este entorno, sintaxis Python y empaquetado ZIP.
No probado: interfaz gráfica de v0.6 en Windows, arranque VBS y compilación de APK con v0.6.
Mantén v0.5 intacta. Si el inicio silencioso no abre, prueba `INICIAR_STUDIO.cmd` para ver el error y envía el registro.
Si JAVA_HOME o ANDROID_HOME no persisten al reiniciar, Harness debe establecerlos solo para este programa, sin alterar otros proyectos.
La compilación automática puede tardar y consume recursos. Desmarca la casilla para trabajar sin compilar al importar.
