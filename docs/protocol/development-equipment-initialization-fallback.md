# Fallback de desarrollo para efectos de equipo no soportados

`WAKFU_DEV_SKIP_UNSUPPORTED_INITIALIZATION=1` permite entrar al combate cuando un efecto de equipo propio está clasificado como `unsupported-native-effect` por el evaluador de bonos. El valor por defecto es0: comportamiento estricto.

El caso confirmado es **Dofus Marfil31361**, efecto379699, familia304, que aplica estado8251. El mismo objeto tiene +1PA y +2PW soportados. El usuario aclaró que equipó Marfil; no hay evidencia de una confusión Ocre→Marfil.

El evaluador de bonos es puro: clasifica el efecto no soportado sin ejecutar ninguna modificación, UID o estado. El fallback omite esa rama completa antes de instalar snapshots. Los bonos soportados permanecen. No se ejecuta parcialmente379699 ni se simula8251. Todos los snapshots del roster se preparan primero, y sólo después se instalan; una validación posterior que falla no publica snapshots ni avisos.

Cada omisión produce `combat_initialization_effect_skipped` con actor/fight, UID de objeto, referencia, ID de efecto, familia y motivo. También se envía un aviso674 al chat del propietario. Los rechazos de entrada, colocación y Ready existentes ahora envían un motivo acotado/escapado al chat, además del registro.

No se omiten plantillas desconocidas, errores de propiedad/equipamiento, errores de aptitudes ni excepciones arbitrarias. Tampoco se omiten innatas o pasivas de baraja. Esa cobertura más amplia requeriría rollback de ejecución de la rama, no este evaluador puro.

Validación:

```sh
PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_combat_initialization_policy.py
PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_combat_actor_snapshot.py
python3 -m py_compile server/local_game_server.py server/wakfu_server/combat/combat_actor_snapshot.py server/wakfu_server/combat/combat_initialization_policy.py
```

Resultados:5 pruebas focales y7 regresiones PASS; compilación PASS. Prueba real del catálogo31361 en Fight de dos actores: modo estricto rechaza379699 sin snapshot parcial; modo desarrollo instalaPA7/PW8, no estado8251, no efectos retenidos parciales y emite diagnóstico exacto. No se probó GUI ni se reinició el servidor durante esta implementación.
