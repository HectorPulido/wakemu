# Solución propuesta — 5

Permitir recolección legal y emitir rechazos que correspondan al estado real del recurso.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Corregir el contrato de propiedad general

La revisión nativa confirma que el tag 56 es `ownerAccount`, pero `resource_packet` envía `creation_time`. Separar ambos conceptos y enviar 0 para recursos públicos. Cubrir tanto publicación como reconstrucción al reconectar; afecta también fresnos y otras especies. Véanse la [causa y prueba ejecutada](REVISION-RESPUESTAS.md). Después capturar el clic para diferenciar bloqueo local de rechazo del servidor.

## 2. Modelar permisos y ocupación

Distinguir dueño del recurso, ocupante temporal, derecho territorial y profesión/etapa. La tabla actual no acredita propiedad. Si los recursos son públicos, no asignar ownership privado por defecto; usar la regla elegida y valores nativos verificados. Reservar la acción con lease y caducidad.

## 3. Crear la ruta vegetal

Decodificar la petición nativa con tamaño/identidad/acción; resolver el recurso en mapa/instancia actuales. Validar alcance, altura, profesión, estado y ocupación antes de mutar. Reutilizar patrones de monster_collect solo para garantías comunes, no sus campos de monstruo como si fueran plantas.

## 4. Confirmar cosecha y recompensas

Cambiar etapa o retirar recurso, consumir herramienta si corresponde y conceder cosecha/XP en una transición recibida una vez. Guardar outbox, productos y estado ecológico. Liberar ocupación al cancelar/desconectar; un reintento no da doble Cardo.

## 5. Emitir estados y errores nativos

Actualizar reserva/etapa para espectadores y productos para dueño. Rechazar recurso ajeno, ocupado o inmaduro con respuesta probada que no cree un aviso genérico erróneo. Al reenviar después de recovery usar el resultado guardado y no inventar ownership.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Solo una cosecha por transición de recurso; ocupación temporal y propiedad no se confunden.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
