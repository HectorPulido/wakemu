# Incoming state carrier and gameplay children

Conclusion: an incoming class310 carrier in cvY does **not** execute its
state's gameplay children. The server must execute the children and emit each
supported result independently. Carrier and child result packets do not cause
the client to apply the gameplay children twice along this receive path.

Evidence from the bundled client, inspected offline with Java22 javap:

1. cvY (message13497) supplies effect class and serialized generic runner.
   cjL.a(cvY) obtains the class prototype from eVi, clones it, assigns the
   local effect context, calls eZR.ds(bytes), and schedules an aTR action.
2. aTR.cby calls the runner's bbq(). Qe.bbq sets bfD=false; Qe.bbs simply
   reads bfD. The receive action explicitly disables authoritative execution.
3. aTR.cbj selects the actor, optionally retains the runner with Qf.p when
   Ty or bbW and the other native guards permit, then calls bbE and fSn.
   It never invokes eZk.c, bbS, or an effect-child execution method.
4. Qf.p only records the runner by instance ID and sets its manager pointer;
   it does not execute children. eZk.bbX/Ty determine retention from the
   state durations/cxj and do not themselves execute effects.
5. The gameplay child loop is in eZk.c(Qe,boolean). It requires positive
   value, rHw, target and manager, resolved state, and bbs()==true. Only
   inside that gate does it iterate fyW.iterator, allocate native eZR child
   instances, initialize their context and execute/schedule them.

The carrier does produce state presentation independently: bbE delegates to
PN.baa().e(runner); for the standalone client context bcz this is bcv.e.
That callback emits ffD state notification for persistent states and updates
the actor's graphical controller through beS/bfb. bfb.b detects eZk and reads
fyW.guL, an iterator of OY HMI actions; this is graphical metadata, not the
fyW.iterator gameplay-child loop. Therefore child result packets should not
be duplicated merely to represent these OY actions.

Probe: sniffer/java/ProbeStateCarrierClient.java executes the real aTR.cbj
with a tracking eZk subclass after the exact bbq operation from cby. Result:
bbs=false, zero gameplay c calls, one observer bbE call. The fixture omits
actor retention and rendering; those paths are established from bytecode,
not simulated live. It does not drive the full action scheduler or UI.

This conclusion is scoped to cvY→cjL→aTR. It does not claim that locally
computed authoritative eZk instances (bbs=true), other initialization paths,
or restored snapshots behave identically. Native carrier retention still
requires valid state metadata and actor resolution on the client.
