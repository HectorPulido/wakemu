Familia20: aumento de máximo HP, eWN
===================================

Registro nativo eVi:20 -> eWN(ffw.sgC), mismo runner común31/AP,41/MP,
191/WP. PC HP aZt=-1: eWN.fU retorna antes de consultar flags de tope.
No se requiere metadata de flags para HP sin tope. AP/MP conservan la
exigencia y límites acreditados. Parámetros eWN:valor,aplicarAlCorriente,
retirarDelCorriente. Se mantiene interpretación común/sentinelas existentes.

Se amplía FAMILIES al stat1 y la escritura del snapshot sincroniza hp/max_hp
además de effect_stats/maxima/base_maxima. No se duplica un manejador por raza.
Paquete13497 yAdditionalDatas10/31/32, retención y13560 usan camino común eWN.
Cambiar máximos/corriente no asigna una fuente de daño o cura inventada.

ProbeNativeHPMaximum.java ejecuta eWN/fff/registro reales:HP60/100 con+25
aplicar/retirar=true pasa85/125 y vuelve60/100. ConfirmaHPsinhardcap.
7pruebas Python máximos pasan incluyendo HP y retirada. Prueba de Ready
SangreTatuada5051 real ya supera20 pero aún rechaza HasEffectWithActionId;
no se afirma Readycompleto. Sin reinicio ni cambios en datos de usuario.
