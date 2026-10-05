# Pruebas — E11

## Resultado registrado

33 tests dirigidos: 32 correctos y 1 error. No es un lote verde. El lote anterior de 133 tests no incluía este módulo de transacciones.

Reproducción propuesta, desde la raíz y en entorno autorizado:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_combat_spell_transaction.SpellTransactionTests.test_server_entry_conditional_spell_damage_and_displacement_share_transaction -v
```

## Casos de aceptación pendientes

| Caso | Resultado exigido |
| --- | --- |
| Geometría sintética coherente | Daño y desplazamiento en preview; original intacto |
| Posiciones reales exportadas | Resolución nativa correcta para altura/radio/jump |
| Consulta desconocida | Error controlado, sin consumo ni paquetes confirmados |
| Colisión exportada None | Comportamiento nativo de colisión, distinto de ausencia |
| Error después de otro efecto | Ningún daño o costo parcial confirmado |
| Commit de operación válida | Una revisión y secuencia, sin repetir efectos |

Ninguno de estos resultados nuevos se da por ejecutado. Guardar estado original, preview, consulta y resultado decodificado.

## Reproducción dirigida y causa acotada

Se repitió el test con instrumentación en memoria: mapa 1134, altura 4, radio 0, jump 4, origen `(2,0,0)` y destino XY `(3,0)`. La consulta y el origen no existen en la exportación de movimiento forzado. Además, ni `(2,0,0)` ni `(3,0,0)` pertenecen a las celdas transitables reales exportadas del mapa 1134.

Esto confirma la incoherencia de la fixture: combina coordenadas de un plano sintético con autoridad de un mapa real. El rechazo no demuestra una carencia del catálogo para posiciones reales. La solución propuesta debe corregir esa coherencia en los tests y conservar el rechazo por consulta desconocida; no relajar el runtime. [Resultado estructurado](probe-consulta.json).
