# Activación de pasivas durante un ciclo real

Resultado offline actual: 339 pasivas instaladas por separado a su primer nivel legal; fuentes estables y originales conservados en339/339 casos. Una carga de catálogos,69,618 segundos. No se operó GUI, DB ni servidor.

La instalación no equivale a activación.184 casos ejecutan efectos atribuibles al inicio nativo;19 muestran ejecución atribuible durante el ciclo posterior.272 ciclos terminan sin excepción y67 encuentran un bloqueo del motor.263 incluyen lanzamiento propio aceptado;89 observan retirada de efectos por expiración real. Estos números no afirman339 pasivas funcionales ni cobertura de todos sus requisitos.

Se usa Ready de producción con innatas y recursos nativos, Wonejo5525 real de nivel1 con habilidad7962 y sus raíces originales en el dispatcher común, turnos/ACK/expiración RuntimeMessages, una pasada propia sin gastar recursos y un lanzamiento normal del deck por prepare_server_spell. El daño entrante real es5; no se alteran PV, resistencias, recursos, estados ni criterios para forzar condiciones. No se fabrican notificaciones de activación.

La pasada sin gastar recursos ocurre antes del lanzamiento: evita perder el evento de fin de turno cuando un hechizo mata legítimamente al Wonejo de12PV. La retirada se observa únicamente mediante relojes reales; no se borra una pasiva permanente para simular un evento.

## Sacrógrito

Sangre Tatuada5051 (nivel10) ejecuta su rama de inicio: PV150→230. El daño original7962 deja225PV. No se cuenta como activación posterior de ciclo. Rastro de Sangre5049, Placidez5050, Libación5193 y Armadura Ardiente7216 muestran ejecución durante el ciclo. Visión7215 y Ejecutor7830 bloquean en IsTriggeredByMeleeEffect; quedan pendientes.

## Primeros bloqueos accionables

| Bloqueo | Casos |
|---|---:|
| Unsupported native predicate: HasSummonWithBreed | 36 |
| Unsupported native numeric predicate: NbAreasWithBaseId | 17 |
| Missing unique native state effect container | 4 |
| No handler for native effect class 1038 | 2 |
| Unsupported native predicate: IsTriggeredByMeleeEffect | 2 |
| Unsupported GetTeamId selector | 2 |
| Unsupported native predicate: GetTriggeringEffectCasterIsSameAsCaster | 1 |
| Unsupported native predicate: IsTriggeredByIndirectEffect | 1 |
| Unsupported HasStateFromUser actor selector | 1 |
| Unsupported native predicate: IsOnSpecificEffectArea | 1 |

Las referencias y fases exactas están en el CSV y JSON. Los36 casos HasSummonWithBreed y17 NbAreasWithBaseId necesitan consultas comunes sobre las autoridades reales de roster/áreas; el auditor no crea invocaciones ni zonas ficticias para eludirlos.

## Límites

El ciclo no garantiza alcanzar umbrales de PV, KO, crítico, curación de un aliado, invocación, captura, zonas, armas o interacciones específicas de clase. Una pasiva sin ejecución observada no se etiqueta como rota. Las condiciones omitidas aparecen en passive_trace/skipped_prerequisites; los intentos de cast rechazados conservan sus motivos y rollback. Sólo se prueba rama normal y primer nivel legal, no todas las combinaciones de deck ni todos los niveles.

La atribución requiere referencia raíz de la pasiva o ascendencia de esa raíz en diagnósticos del dispatcher. Registro subscribed_waiting_event se excluye de activación. Una ejecución puede instalar efectos o emitir paquetes sin cambiar PV; el JSON conserva la traza y recursos antes/después para distinguirlo.

## Reproducción

```sh
PYTHONPATH=server python3 server/tools/audit_passive_activation.py --output docs/reports/combat-inventory/passive-activation-all-current.json
```

El primer foco Sacro con casts tuvo hashes inestables y permanece histórico; no se usa en los conteos finales. La matriz339 reemplaza ese checkpoint.
