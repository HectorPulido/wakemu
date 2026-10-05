# GetContainerLevel

Token106 del cliente se construye como `eJE`. Su método `d(Object,Object,Object,Object)` convierte el **tercer argumento** a `eZR`: si es null devuelve cero; en caso contrario devuelve `eZR.fRR()` ampliado de short a long. Un tipo ajeno produce ClassCastException. No consulta el runner que originó un evento.

`eZR.fRR()` usa primero el contexto PS/eVt actual: `Oh()!=-1` se convierte a short. Con contexto ausente o valor sentinel -1, consulta PL/eVo; PL null devuelve cero, PL presente devuelve `cmZ()`. El nivel del personaje o el nivel de evaluación del hijo no sustituyen ese objeto.

`combat_container_level.running_container_level` usa el contexto actual de la invocación, el contenedor fyW resuelto por UID/scope o el fyF explícito del plan de lanzamiento. Un contenedor directo requiere presencia acreditada y nivel explícito; datos incompletos siguen desconocidos. El adaptador aporta un callback diferido para que otras condiciones no fallen por exigir datos no utilizados.

`ProbeNativeContainerLevel` llama al eJE original y valida seis casos: runner null, PL200, override65538→2, sentinel→200, PLnull→0 y tipo inválido. Pruebas Python cubren ausencia de autoridad, selector inválido y prioridad sobre datos ajenos del evento. Esto acredita cálculo y ruta de condiciones, no todos los efectos que las siguen.

Auditoría focal de 15 casos anteriormente bloqueados: 8 cambian estado del actor; 5 avanzan hasta propagación de lifecycle de invocados no auditada y 2 hasta flags de grupo15 no admitidos. Ninguno mantiene GetContainerLevel como bloqueo. Todos preservan el original y los hashes de fuentes son estables: `.runtime/local/container-level-focal.json`.
