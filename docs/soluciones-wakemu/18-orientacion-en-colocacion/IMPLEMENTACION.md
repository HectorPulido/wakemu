# Issue18 — Orientación durante colocación

El consumidor nativo cjx/cvL13494 crea aTU y entrega la acción al scheduler del encuentro. aTU aplica facing al actor sin exigir active, turno o gastar recursos. dbh, activo durante fightPlacement, emite la misma petición13655 para los cuatro cardinales. No se agregó un carrier inventado ni campos a13652.

combat_orientation.apply ahora separa placement de active. En placement valida ownership, ready_owners, celda del equipo y ausencia de ACK pendiente; no exige turno. La rama active conserva _current_owned y la barrera ACK. Finished rechaza. El mensaje se valida antes de cambiar facing/contador y sigue enviando13494+flush13420. No modifica hechizos.

Pruebas delegadas a Luna: cardinales, ready/foreign/ACK/phase/celda, PA/PM/turnos y persistencia. Fuente aún no cargada. El dispatcher actual responde al solicitante: multijugador/observadores se validarán con los issues14/16; no se declara sincronización de varios clientes.

## Validación del servidor

Luna ejecutó test_combat_orientation y test_fight_checkpoint_store en Docker PostgreSQL aislado: **13 pruebas pasan**. Incluye cardinales, ownership/ready/ACK/fase/celda, ausencia de consumo, dirección conservada al iniciar combate y JSON de checkpoint tras reapertura. El carrier se cotejó con bytecode y probes nativos de petición/respuesta para cuatro direcciones. Esto no sustituye visual ni observadores. Construcción en curso; carga se coordina con el smoke del cliente para no cortar la sesión audit.

Corrección cargada en world mediante build/recreación; Docker confirma healthy. La prueba visual sigue pendiente. No se declara resuelta la publicación a observadores, que pertenece al ciclo multijugador.
