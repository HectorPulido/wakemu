# Solución propuesta — 4

Hacer que la probabilidad autoritativa y la disponible para presentación describan la misma regla, sin tocar el cliente.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Separar regla de ayudas de prueba

Registrar versión y flags efectivos del servidor y perfil que usa el usuario. El agente OpenPlanting altera retornos del cliente; la restricción actual impide corregirlo aquí. Documentar una prueba sin ese override solo si hay perfil/configuración existente autorizado, no editar el JAR. El porcentaje de una instalación intervenida no demuestra la fórmula del servidor.

## 2. Construir contexto autoritativo

Resolver tipo de suelo, semilla/recurso, profesión, clima y estado ecológico de la celda. Decodificar qué valores usa el cliente para calcular su porcentaje y qué carriers se deben sincronizar. Separar permiso de iniciar, probabilidad de éxito y consumo en fallo; son decisiones diferentes.

## 3. Definir fórmula versionada

Especificar escala (0–1 o 0–100), redondeo, clamps y entradas. Reutilizar exactamente ese cálculo para decidir y comunicar contexto. Persistir versión y probabilidad del intento para que cambios de clima posteriores no reescriban el resultado. No afirmar una fórmula oficial mientras falten catálogos/reglas.

## 4. Aplicar RNG una sola vez

Validar y reservar antes de tirar; almacenar draw/resultado en recibo. Reintento no obtiene otra oportunidad ni vuelve a consumir. Fallo devuelve el resultado nativo probado y sigue la política definida de consumo; éxito confirma recurso y semilla juntos.

## 5. Validar presentación y distribución

Probar probabilidades extremas y valores fronterizos con RNG fijo, después distribución de muchas tiradas independientes. Comparar datos enviados con texto visible en perfil compatible. Si override local conserva texto incoherente, registrar ese límite sin dar la solución de servidor por defectuosa o terminada.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Permiso no equivale a probabilidad; repetir una solicitud no vuelve a sortear el resultado.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
