# Solución del servidor

Separar13744 de los mensajes de texto puro; leer i64 guild_id seguido de u16longitud en bytes UTF8 y texto, con consumo completo del cuerpo. Validar guild_id contra sesión y membresía autoritativa al integrar el handler. No confiar en la pertenencia afirmada por el paquete. El ID de gremio no es ID de party. Esto arreglaría el contrato, pero aún faltaría routing y respuesta del canal. No hubo cambios de código.
