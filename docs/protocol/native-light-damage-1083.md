# Daño de Luz, familia 1083

La factoría `eVi` crea `eXt(eVg.rpk, far.rJU)` para 1083: **Luz**, no Stasis. El identificador de familia se conserva en el encabezado del mensaje 12613; el elemento utilizado para calcular resistencias no sustituye ese identificador.

`fau.fSy` resuelve Luz mediante `eYE.a(source)` antes de comprobar la máscara de coeficientes: selecciona la mayor característica elemental presente del lanzador. El orden de desempate de `eVg.values()` es fuego, agua, tierra, aire. La resistencia del objetivo corresponde al mismo elemento seleccionado. Stasis tiene otra rama, que busca la menor resistencia del objetivo; esa rama no está habilitada mediante 1083.

`eXt.n(eVg.rpk)` y la tabla `eXu` añaden el evento 11. No se emite el evento fuego/agua/tierra/aire derivado de la selección aritmética.

Implementación común: `combat_damage_healing.DAMAGE_FAMILIES` registra 1083 en el manejador, la preparación de la factoría y el codec. `light_damage_element` exige al menos una característica elemental presente; no inventa un elemento cuando el snapshot carece de ellas. Los contextos de daño, flags, recursos, callbacks y transacciones siguen siendo los comunes de eXt.

Validación offline: `ProbeNativeLightDamage` ejecuta el fau original con maestrías fuego100/agua200 y resistencia agua100. Las máscaras 0/1/2/3 producen respectivamente 100/300/81/243, exactamente iguales al elemento agua explícito. También verifica empate negativo en favor de fuego y evento11 del runner original. Se ejecutó con JDK22 y el cliente local, sin servidor oficial.

`PYTHONPATH=server:server/tests python3 -m unittest test_combat_light_damage test_combat_damage_handler test_combat_damage_events -q`: 14 pruebas pasan, incluida aplicación de recursos y encabezado 1083. La prueba de arma real y su rollback se registra por separado en el pipeline 12889; estas comprobaciones no afirman funcionamiento de todas las armas ni implementan Stasis.

## Stasis917

Integración posterior: eVi crea eXt(eVg.rpj,far.rJU) para917. fau.fSy resuelve por separado eYE.a(caster), mayor maestría, y eYE.b(target), menor resistencia presente; desempates siguen fuego,agua,tierra,aire. Ambas selecciones ocurren antes de aplicar bits de coeficientes. El motor conserva917 en mensaje12613 y evento9 (eXt.bbx original), sin sustituirlo por el elemento escogido para el cálculo. Datos originales de actores permanecen intactos.

ProbeNativeStasisDamage.java reproduce resultados100/300/100/300 para máscaras0..3 con maestríaagua200 y resistenciafuego0; nueve pruebas Python de Stasis/Luz/eventos pasan. La integración reutiliza daño, absorción y eventos existentes. No acredita aún el ciclo Steamerator ni los hechizos completos del Steamer; falta prueba gráfica.
