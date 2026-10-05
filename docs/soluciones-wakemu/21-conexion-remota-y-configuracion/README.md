# 21. Tools con configuración `.env` del servidor

Documentar contrato de endpoints y acceso externo del servidor; conservar fuera de scope cualquier cambio de cliente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. No se ha implementado esta solución. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

32 y E03 antes de exposición externa. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Bind y anuncio son distintos; acceso de red nunca reemplaza autenticación ni autoriza publicar assets del cliente.
