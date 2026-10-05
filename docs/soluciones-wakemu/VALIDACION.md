# Validación de la auditoría documental

## Pruebas ejecutadas

Comando de base ejecutado durante la auditoría:

```sh
PYTHONPATH=server:server/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_planting test_planting_runtime test_planting_context test_monster_wander test_monster_collect test_profession_store test_combat_rewards test_combat_orientation test_combat_placement_cells test_chat_console test_social test_haven_bag test_haven_bag_store test_inventory_bags test_inventory_move test_inventory_elements test_builds test_aptitudes test_build_journal test_combat_groups test_combat_group_store test_combat_monster_world test_fight_checkpoint_store -q
```

Resultado: **133 tests descubiertos, 123 pasaron, 10 omitidos; salida 0; 12,641 segundos**. Las omisiones corresponden a pruebas que necesitan Redis real. No se ejecutaron aquí los escenarios futuros de los planes. Los ensayos gráficos y probes anteriores están contextualizados en el informe original; no se cuentan como parte de este lote.

## Cotejo y límites

Se verificó existencia de fuentes y tests vinculados, funciones ancla mediante AST, hashes del checkout y correspondencia específica entre brechas y planes. Los fragmentos son código del servidor; no se distribuyen assets ni binarios del cliente. El commit no representa por sí solo los cambios sin confirmar de este checkout.

Cada carpeta tiene README, DIAGNOSTICO, COTEJO, SOLUCION, PRUEBAS y FALTANTES. La validación de integridad de enlaces y cobertura documental se registra aparte en revision-documental.json. No equivale a implementación o aceptación de las funcionalidades pendientes.

## Comprobaciones semánticas adicionales

Se ejecutaron **16 comprobaciones confirmadas** del código actual, incluyendo serializers de builds en memoria, orden SQL/overlay, orden de autenticación API, presencia de rutas, consumidores de deck, orientación, continuación de abandono y configuración de tareas. Resultados y límites: [comprobaciones-codigo.json](comprobaciones-codigo.json). Son pruebas del diagnóstico actual, no de las soluciones propuestas.

## Lote adicional tras cambios concurrentes

Se repitieron cinco módulos relevantes: test_inventory_elements, test_inventory_move, test_builds, test_aptitudes y test_combat_spell_transaction. Resultado: **33 tests, 32 correctos y 1 error**, 18,714 segundos. El error de terreno no exportado está documentado en [E11](E11-test-desplazamiento-sin-terreno-exportado/README.md). No se declara correcta la suite completa.

Se recotejaron nueve fuentes que cambiaron durante esta revisión; el manifest conserva hashes anteriores y revisados. Si vuelve a cambiar el checkout, las conclusiones deben evaluarse contra los bytes identificados, no contra HEAD solamente.
