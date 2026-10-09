Mini launcher para el servidor privado Wakfu · macOS y Linux

Descomprime mini-launcher dentro de la instalación existente de Wakfu, al lado
 de lib/, contents/, jre/, config.properties y classpath. Abre Launch.command.
Usa cuentas del servidor privado; este launcher no usa el Ankama Launcher.

Requisitos: cliente instalado compatible con Java 21, macOS con sandbox-exec,
Python 3 con Tkinter. El ZIP incluye exclusivamente código y agentes propios.
No contiene el cliente, su Java, librerías, mapas, contraseñas, tokens ni capturas.
No necesita un JDK para ejecutarse. Windows aún no está implementado.
Linux usa jre/bin/java y requiere DISPLAY (X11/XWayland) y permisos de la
sesión gráfica; ejecuta bash run-client.sh desde una terminal de escritorio.
En Linux el aislamiento usa el guard Java obligatorio, sin sandbox del sistema
operativo: el bridge Python y las bibliotecas nativas quedan fuera del guard.
El launcher muestra esta diferencia al validar y al abrir el juego.

Configura config.json antes de abrir: api_url, server_host (IPv4 numérica),
dispatch_port, game_ports, chat_port y http_port. El valor inicial es localhost.
Para otro equipo, el servidor también debe anunciar su IP/puerto del mundo;
cambiar este JSON no modifica la dirección que el servidor envía al cliente.
Los demás destinos y la resolución DNS externa se bloquean. No incluye sniffer.

Validación sin abrir el juego: bash run-client.sh --check.
Si macOS bloquea Launch.command descargado, revisa su origen y ejecútalo desde
Terminal con bash. Este paquete no elimina automáticamente cuarentena del sistema.

Preferencias/cache/logs y tokens nuevos se guardan solo en profiles/ dentro del
mini launcher. Los archivos oficiales se enlazan para lectura y no se modifican.
El paquete no tiene actualizador. Los agentes usan clases del cliente actual;
una versión distinta requiere volver a validarlos.

Plantación libre para pruebas locales:
config.json incluye "open_planting": true. El launcher carga nuestro agente
open-planting.jar y permite intentar cualquier semilla. Para recuperar las
restricciones del cliente, cambia a false y vuelve a abrirlo. El servidor debe
usar WAKFU_OPEN_PLANTING=1 para aceptar esta política de pruebas. El agente no
incluye archivos del cliente oficial ni desactiva el aislamiento de red.
