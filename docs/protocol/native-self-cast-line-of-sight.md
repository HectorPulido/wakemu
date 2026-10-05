# Línea de visión de lanzamiento sobre la propia celda

`fcj.a(PV,eVo,...)` realiza LOS por `fcr.a`, no omite la validación por nombre de hechizo. `fcr` eleva el origen por trunc(height*0.8) y prueba un segundo extremo elevado al menos6 si el primer rayo falla. Estos rayos de lanzamiento no son el rayoSf bare de altura cero exportado en el catálogo estático.

`ProbeNativeSelfCastLOS` carga VB reales de1134 y llama fcr.a original en la mismaXYZ(-8,-7,-1) con alturas0,6,40. Los tres resultados sontrue y ninguno consulta bloqueo dinámico. El catálogoSf bare devuelvefalse para ese mismo par37/37. Por eso exigir ese par bare en `_validate_target` producía un rechazo previo al efecto, aunque el algoritmo de lanzamiento nativo lo acepta.

El guard común acepta el resultado nativo propio únicamente con XYZidénticos y conserva terreno, rango, recursos y freecell. Para otra celda sigue exigiendo el callback de LOS verificado. No se agrega un parSf visible inventado ni se cambia `static_visible`/`authoritative_visible`, ni existe excepción5031/raza. Tres regresiones verifican propioXYZ, exteriorbloqueado y guards rango/recursos/freecell.

Bytecode: .runtime/local/native-self-cast-fcj.txt y native-self-cast-fcr.txt. La GUI/reinicio pertenece al checkpoint del agente principal; este cambio no reinicia servicios.
