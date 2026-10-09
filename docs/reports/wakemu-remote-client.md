# Conexión remota de Wakemu

## Conexión directa opcional

El mini-launcher existente permite IP y puertos explícitos y limita su guard
Java y sandbox a ellos. El launcher local conserva localhost. Para conexión
directa configura una IP IPv4 del servidor y un certificado HTTPS confiable
con esa IP en su SAN. Usa un certificado propio autorizado; no desactives TLS.

En el servidor, revisa la configuración sin iniciar servicios:

```sh
export WAKFU_REMOTE_HOST=192.168.1.50
export WAKFU_REMOTE_BIND_IP=192.168.1.50
export WAKFU_REMOTE_TLS_CERT=/ruta/absoluta/remote.crt
export WAKFU_REMOTE_TLS_KEY=/ruta/absoluta/remote.key
docker compose -f compose.yaml -f compose.remote.yaml --profile remote config --quiet
```

Las rutas del certificado son ejemplos que debes sustituir. Cuando decidas
activar esa configuración, el comando es:

```sh
docker compose -f compose.yaml -f compose.remote.yaml --profile remote up -d --no-build
```

Publica sólo dispatcher 15558, world 15556 y un proxy HTTPS 18443 que permite
exclusivamente POST `/login`, `/remember` y `/game-token`. La API completa sigue
en localhost:18081. PostgreSQL y Redis siguen sin puertos publicados. Requiere
Compose 2.24.4 o superior para `!override`. Los puertos se pueden cambiar con
`WAKFU_REMOTE_DISPATCH_PORT`, `WAKFU_REMOTE_WORLD_PORT` y `WAKFU_REMOTE_AUTH_PORT`;
refleja esos mismos valores en el cliente. No se han iniciado estos servicios.

En el Mac cliente, genera y extrae el mini-launcher dentro de tu instalación de
Wakfu según su README. Copia `config.remote.example.json` como `config.json` y
cambia IP/puertos/ruta de instalación. Desde su carpeta:

```sh
python3 remote-login.py
bash run-client.sh --check
bash run-client.sh --token-file profiles-remote/remote-login-session.json
```

Esperado: login HTTPS correcto, guard validado y selección de personajes del
servidor remoto. Prueba mapa, inventario y combate completos, sal y vuelve; no
debe cambiar tu progreso. La sesión se guarda con permisos 0600, sin contraseña.

## Verificación automatizada del proxy

Verificación automatizada del proxy, independiente de world:

```sh
python3 server/tools/remote_auth_proxy_smoke.py
```

Usa nginx efímero sin red ni puertos publicados, un certificado temporal y un
upstream falso. Comprueba POST login/remember, reenvío del bearer de game-token,
401 sin bearer, GET rechazado y rutas ajenas bloqueadas. Sólo verifica el proxy;
no sustituye probar autenticación real, certificados confiables o conectividad
entre equipos. El certificado autofirmado de esta prueba aislada se acepta
únicamente dentro del contenedor de prueba; el cliente remoto verifica TLS.

## Alternativa SSH

Esta alternativa mantiene los puertos del servidor en localhost. SSH transporta
dispatcher (15558), world TLS (15556) y autenticación local (18081); no publica la
API, PostgreSQL ni Redis. El advertise del servidor debe seguir en `127.0.0.1`
y el puerto world en `15556`. No requiere cambiar Compose ni certificados TLS.

En el otro Mac necesitas el checkout y los assets del cliente, sus requisitos
habituales (JDK 21 o superior), y acceso SSH al equipo que ejecuta Wakemu.
Configura ese acceso con una clave SSH y compruébalo primero:

```sh
ssh hector@IP_DEL_SERVIDOR true
python3 client-tools/remote-client.py --ssh hector@IP_DEL_SERVIDOR --check
python3 client-tools/remote-client.py --ssh hector@IP_DEL_SERVIDOR -- --profile remoto
```

Sustituye `hector@IP_DEL_SERVIDOR` por tu usuario y dirección SSH reales. También
puedes usar un alias de `~/.ssh/config`. El launcher pide las credenciales de la
cuenta de juego como siempre. Los puertos 15556, 15558 y 18081 del Mac cliente deben
estar libres; el wrapper rechaza un world local para evitar conectar al servidor
equivocado. Mantén esta terminal abierta mientras juegas; al salir se cierra el
túnel. Para terminarlo manualmente, pulsa Ctrl+C.

Prueba completa: entra con tu cuenta, selecciona personaje, cambia de mapa,
abre inventario y combate contra un monstruo; espera el mismo comportamiento
que en local. Sal del cliente y verifica que el proceso SSH del wrapper termina.
`--check` sólo imprime comandos; no conecta ni reinicia servicios.
