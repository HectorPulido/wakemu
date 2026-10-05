# E17 — Monturas equipadas que no permiten montarse

La captura muestra un dragopavo equipado, el bonus de 28 de dominio y el botón de montar deshabilitado. **Equipar y montarse son recorridos distintos.** El servidor admite la referencia en equipo, pero carece del estado y operaciones de montura.

Preferencia explícita: **desbloquear monturas por defecto, sin exigir la misión**. Esto no implica regalar un dragopavo ni eliminar automáticamente su requisito de nivel.

[Diagnóstico y cotejo](COTEJO.md) · [Solución concreta del servidor](SOLUCION.md) · [Pruebas ejecutadas y aceptación](PRUEBAS.md) · [Evidencia](probe-monturas-nativo-y-servidor.json).

Auditoría, sin implementar fixes. Dependencias: 34/E05 (equipo activo), E01 (persistencia), 0 (movimiento) y E14 (accesos rápidos, si se añade allí el control). No incluye cambios de hechizos.
