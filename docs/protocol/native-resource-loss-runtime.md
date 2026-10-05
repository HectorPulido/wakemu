# Pérdida de PA/PM: checkpoint de implementación

Familias 48 (PM) y 55 (PA) tienen manejador común `combat_resource_loss_handler.py`, registro en factoría, cálculo eVZ, contexto eVt, probabilidades fNa, codec eVZ, efectos propios y retirada signed nG. No son alias del manejador eWR.

Pruebas: 25 tests focales de handler/helpers/eventos/timing; decodificación original Java de paquetes cvY/eVZ 48 y 55; probe original de SQ positivo y negativo y retirada inversa. Un fixture de codec del test usa timing vacío y necesita sustituirse por `native_time_payload`; los paquetes del probe y producción llevan timing válido.

Focal de hechizos 2015/6260 (niveles 1/200): cuatro transacciones terminadas, fuentes estables y originales preservados. No demuestra pérdida positiva de PM: algunos monstruos mueren con el primer daño o el sorteo produce cero.

Focal adicional 2015 con Tofu nativo ref4/nivel10 (HP58/PM6): pérdida PM6→5 y creación del estado5227 nivel10, caster/target/manager del receptor, característica86=10. El hechizo completo rechaza después el hijo385972/familia41 por `Missing native triggering maximum amount`; se conserva rollback de ambas transacciones. Esto acredita la ejecución privada de 48+5227, no un casteo completo aceptado.

Pendientes antes de cerrar cobertura: rama parámetro−1/fWf y cota invertida GS.a(0,−1) (probe nativo mostró resultado−1), selección de eventos comparando el valor anterior a la cota original, evolución de recursos durante reacciones L2 y suscripciones de estas familias. No se afirma soporte completo ni comprobación GUI. La prioridad pasó a armas básicas por petición del usuario; no se ampliaron estas ramas.
