# Pruebas

Ejecutado: encoder cms con gremio456 y texto UTF8; frame nativo26bytes, payload19bytes. El decoder actual lanza `17 undecoded bytes`. Los otros siete requests de chat sí coinciden con su layout.

Pendiente para el fix: roundtrip preservando ID/texto; ID de gremio positivo con bytes superiores no cero; truncados antes/dentro del i64 y texto; longitud falsa; gremio ajeno; no membresía; routing solo a miembros; límites/eco. No probar únicamente fixture con ID0.
