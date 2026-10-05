# E11. Prueba de desplazamiento sin consulta de terreno exportada

El lote dirigido de revisión ejecutó 33 tests en 18,714 segundos: 32 correctos y 1 error. Falló test_server_entry_conditional_spell_damage_and_displacement_share_transaction con ValueError: Native forced terrain source/query is not exported. No se aplicó ninguna corrección.

[Diagnóstico](DIAGNOSTICO.md) · [Código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Faltantes](FALTANTES.md)

Este hallazgo es una brecha de validación confirmada. No demuestra todavía un defecto de desplazamiento en el mapa real. Relacionado con 0 y 34 por la necesidad de validar transacciones y combates con geometría real.

La reproducción dirigida confirma que la fixture usa coordenadas sintéticas que no pertenecen al mapa real anunciado. Ver el cotejo y el probe antes de cambiar el runtime.
