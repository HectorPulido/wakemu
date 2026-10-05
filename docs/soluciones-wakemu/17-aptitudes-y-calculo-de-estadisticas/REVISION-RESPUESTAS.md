# Revisión de respuestas — aptitudes y estadísticas

## Cobertura actual comprobada

Los cuatro tests actuales de `test_aptitudes.py` pasan: presupuestos por categoría, caps/duplicados, persistencia con rechazo atómico y combinación de porcentajes de vida con equipo. No acreditan que todas las aptitudes funcionen.

Se evaluó por separado un punto en cada entrada de las categorías del catálogo a nivel200, sin combate ni hechizos. [Resultados y hashes](probe-cobertura-bonus-actual.json):24 entradas producen estadísticas o porcentajes; **7 son aceptadas pero devuelven `unsupported` sin bonificación**:3,4,17,21,27,36,39. Las cuatro referencias24,25,32,33 aparecen en listas de categorías pero no en el catálogo de bonos y se rechazan. No afirmar que estas últimas sean opciones seleccionables: puede haber referencias obsoletas que la UI filtra.

Todos los siete casos no evaluados usan generic330/runner`eYg`. Los IDs3/4 y otros tienen parámetro0; **eso no demuestra efecto cero**. `eYg.C` busca `fyE.aag(effect.aZE())`, obtiene un contenedor de efectos hijo y lo ajusta al nivel mediante`fyD.cq`; posteriormente recorre/aplica sus efectos. El catálogo resumido de parámetros del padre no contiene esas bonificaciones. Los bonos17 y36 además tienen criterio. Falta extraer sus hijos y condiciones: no convertir generic330 en un stat inventado ni tratarlo como éxito sin efecto. La inspección fue estática del runner para aptitudes; no se ejecutaron pruebas de hechizos.

## Presupuesto y build activa

`validate` acepta nivel de hoja−1 o exactamente`character.level`, y calcula presupuesto con ese nivel. No usa`effective_level`. Por ello no acredita modulación: una hoja vinculada a otro nivel se rechaza aunque corresponda a una build modulada legítima. La solución debe resolver primero el nivel autoritativo de la hoja mediante el modelo de builds, sin confiar en el valor enviado por el cliente. Validar categoría, máximos y presupuesto sobre ese nivel antes de guardar.

La evaluación toma`active_build_index` o0, mientras la selección persistida sigue pendiente en34. Guardar otra hoja no demuestra que sus aptitudes sean las activas. Unificar selección, equipos y aptitudes en una revisión durable de build y conservarla al reconectar; no sumar dos hojas ni aplicar deltas sobre un resultado ya bonificado.

## Vida y reversibilidad

`effective_character` recalcula vida base desde raza/nivel, añade el plano y después el porcentaje, con división entera hacia cero y mínimo1. Repetirlo no acumula porcentajes. El fixture actual de nivel6/raza8 pasa de110 a118 con dos puntos de vida y a125 con amuleto2021. Eso acredita esa combinación, no todos los caps/estadísticas.

La [prueba de reversibilidad](probe-reversibilidad.json) ya registró curación al retirar/reponer puntos mientras se estaba herido, tanto SQLite como MemoryRedis. El problema no es acumulación del máximo: guardar la hoja pasa por el ajuste persistente de salud y el clamp pierde el déficit previo. Ver E12 para el criterio de conservar salud; no usar cambios de build como regeneración gratuita. La edición de una build secundaria tiene una prueba separada en34 y no cambia salud en aquel caso.

## Solución y pruebas que faltan

Ampliar el catálogo con hijos de los siete efectos y su criterio/escala por puntos. Derivar un resultado puro desde base+equipo+aptitudes de una sola build; comprobar qué estadísticas llegan al snapshot y al modelo del servidor, no solo que aparezcan en un diccionario. Para cada bono, conservar una comparación numérica nativa acreditada antes de añadir soporte. Recalcular salud bajo una regla explícita sin curación, con transacción de hoja/selección/estado y recibo recuperable.

Faltan hijos/criterios, modulación, condiciones de respec acreditadas, reparto de categorías con nivel efectivo, snapshot visible fuera/dentro de combate y rechazo nativo coherente. No copiar una restitución libre como regla oficial; guardar hojas actualmente no comprueba autorización de respec. No se aplicaron fixes. Hechizos y su integración siguen reservados a la otra sesión.
