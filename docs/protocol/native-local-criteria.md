# Variables locales y condicionales nativos

El parser instalado `eQd.fGw` guarda `alS` en `qEJ` (`HashMap.put`); `fGA` recupera ese árbol mediante `get`. No es una asignación ejecutada durante el combate. `a=1; b=a; a=2; b==1 and a==2` evalúa verdadero en el cliente instalado. Un nombre aún no definido genera `alR`.

`fGx` construye `alE.a(condition, yes, no)`. Requiere condición booleana y ramas de igual categoría nativa. Para números crea `alF`: `bDl` requiere ambas ramas integrales; `d/e` evalúan exclusivamente la rama seleccionada. Con una rama double el resultado usa double incluso si se seleccionó una rama long. Los operadores long conservan overflow firmado de64bits. Literales se leen como long, no entero de precisión ilimitada.

`sniffer/java/ProbeNativeLocalCriteria.java` ejecuta el lexer/parser/evaluador reales sin acceder a la red. Su prueba acredita alias previos a reasignación, condicional anidado, overflow y ramas int/double.

El intérprete restringido `combat_local_criteria.parse_local_criterion` produce un AST para el evaluador permitido existente; no ejecuta Python. Los alias se expanden con la versión visible en su declaración. El ámbito termina al evaluar cada criterio. `combat_conditions` conserva validación de todas las ramas: una función no implementada sigue siendo desconocida, mientras que contexto ausente en una rama conocida no seleccionada no se consulta. Esto conserva el rechazo explícito y evita inventar estados del mundo.

28/28 criterios históricos con declaraciones de variables parsean. Eniripsa6967 necesita además `GetSpecificEffectAreaCountInRange`; su parsing y costes locales están comprobados pero el casteo completo permanece pendiente de esa autoridad.
