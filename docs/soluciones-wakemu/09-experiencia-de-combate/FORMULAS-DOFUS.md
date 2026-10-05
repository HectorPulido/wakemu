# Fórmulas de referencia: código Dofus indicado por el usuario

Fuente leída: `/Users/hectorpulido/dofus/starloco-game/src/org/starloco/locos/`. No se ejecutó ni modificó Dofus. [Hashes exactos](probe-fuentes-dofus.json). Esta es la implementación de referencia solicitada; no se afirma que coincida íntegramente con un servidor oficial.

## XP: entrada, datos y reparto

`dynamic/FormuleOfficiel.java::getXp` se llama desde `fight/Fight.java:5111`. La base `groupXp` es la suma de `MonsterGrade.getBaseXp()` de los enemigos perdedores; `MonsterData` carga esos valores desde la columna`exps`. **No son datos de botín de Wakfu ni deben mapearse por coincidencia de IDs entre juegos.** En Wakemu hace falta un catálogo de XP base por referencia/nivel, usando una política del emulador si la base no está en el cliente.

Definiciones exactas de esa función:

- `W = nivel_personaje * 0.5 + sabiduría_total`.
- `N` cuenta ganadores con jugador, excluyendo invocaciones, monstruos, recaudadores y clones; se limita a8. Cero devuelve0.
- `nbonus` cuenta ganadores con jugador cuyo nivel es **estrictamente mayor** que`nivel_jugador_máximo / 3` (división entera en el llamador). Se limita a8. La tabla`B` para0..8 es`[0.5,0.5,2.1,3.2,4.3,5.4,6.5,7.8,9]`.
- `R = suma_niveles_perdedores / suma_niveles_ganadores`. Si la lista completa de ganadores tiene tamaño1, se fuerza0.6. En otro caso0 devuelve0; entre0.9 y1.1 inclusive se fija1; fuera de esa banda, invertir cuando sea mayor1 y aplicar mínimo0.01.
- `Q = max(sumas_niveles) / min(sumas_niveles)`. Mínimo no positivo devuelve0. SiQ<3, fijar1; en otro caso invertirQ. Acotar a0..1.

La expresión de XP de jugador es:

```text
trunc_long(
 (1 + W/100)
 * (1 + trunc_int(challenge/100))
 * (1 + trunc_int(star/100))
 * (B + R) * Q
 * trunc_long(groupXp/N)
 * (nivel != 199 ? Config.rateXp : 1)
 * conquista
)
```

**Los cocientes challenge/100 y star/100 son enteros en Java.** Así50 % en esas entradas no aumenta ese factor;100 % lo duplica. `groupXp/N` también trunca antes de multiplicar. No sustituirlos silenciosamente por una fórmula decimal al afirmar que se clonó este código. La función después duplica XP en modo heroico bajo el nivel anterior a la muerte, y multiplica1.2 con truncado para suscriptor si nivel!=199. El llamador aplica además bonus de brecha y deducciones de gremio/montura. Wakfu requiere mapeo explícito de esos modificadores: no inventar suscripción, conquista o montura equivalentes.

Para Wakemu: mantener el esqueleto de reparto y poner el multiplicador solicitado en una tabla de política versionada. La opción de compatibilidad literal debe conservar estos truncados; cualquier corrección deliberada debe identificarse como política nueva. Conservar la curva nativa de niveles de Wakfu, su cap y sus carriers; copiar XP de Dofus no significa copiar sus umbrales ni su excepción de nivel199.

## Drops: fórmula y condiciones del servidor Dofus

`database/data/game/DropData.java` carga tabla`drops`: `monsterId`, `objectId`, `percentGrade1..5`, `ceil`, `action`, `level`. `World.Drop.copy(grade)` elige porcentaje por grado; dato fuera de rango no genera drop. `monsterId=0` añade una regla global a todos los monstruos. La fuente de probabilidades para **Wakfu** será su propia enciclopedia, no esta tabla de Dofus.

`Fight` suma prospección de quienes`canLoot()`, aplica el factor de desafío a ese total y compara el umbral`ceil * rateProspectThreshold`. Prepara una fila por enemigo elegible, excluyendo invocaciones. Luego ordena participantes por prospección descendente y baraja filas para cada uno. La tirada ordinaria es:

```text
draw = Math.random() * 100
chance = porcentaje_del_grado * max(1, prospección_personal/100.0)
       * conquista * desafío * estrellas * Config.rateDrop * bonus_brecha
éxito si draw < chance, sujeto a la acción/condición de la fila
```

Desafío usa`1 + max(1,suma_bonus_drop)/100.0` en este código; incluso sin desafío produce1.01. Estrellas usa`max(1,1 + bonus/100.0)`. No hay clamp explícito de chance: superar100 garantiza éxito. Acción−2 es única y elimina la fila del pool tras concederla; acción8 obtiene cantidad aleatoria de su condición. Acciones de mapa, alineamiento y quest se evalúan aparte. `rateProspectThreshold<=0` es el modo privado de drop libre y evita varios bloqueos, pero mantiene probabilidades. No copiar esa excepción a Wakfu ni equiparar automáticamente estas acciones a sus condiciones nativas.

## Kamas: fórmula y discordancia del llamador

`common/Formulas.java:740` declara`getKamasWin(..., maxk, mink)`: incrementa maxk, calcula`trunc(Math.random()*(maxk-mink))+mink` y aplica`Math.round(... * Config.rateKamas)`. Con argumentos correctos genera un entero uniforme en[min,max]. `Fight` suma min/max de enemigos no invocados.

**El llamador observado pasa `(kamas.first, kamas.second)` pero construye esa pareja como `(minKamas,maxKamas)`**. Por tanto, el orden está invertido respecto a la firma. No presentar el recorrido existente como una tirada uniforme correcta: para min10/max20, la expresión literal es`trunc(U * -9)+20`, con resultados12..20 paraU∈[0,1); si min=max conserva ese importe. Los casos extremos deben verificarse al portar; la solución de Wakemu debe usar parámetros nombrados `minimum`/`maximum`, validar el rango y tirar inclusivamente una vez por recibo, conservando explícita esta diferencia respecto al bug de referencia.

## Integración pendiente, ya con fuentes identificadas

Guardar multiplicadores de XP/drop/kamas en BD con versión; congelar participantes, enemigos, base y modificadores al resolver combate. Persistir tiradas y resultados antes de emitir resumen. No ejecutar esta fórmula dentro del callback de cada cliente ni repetir tiradas al reconectar. La cobertura pendiente es integración y reproducción, no localizar la función solicitada.
