# Active owned reconnect: native turn presentation

Read-only source investigation. Current sequence12847/cvb →12233/cvk →12514/cvx(ACTION) →12053/cvn restores the native active timeline and the owned input controller without synthesizing13337/13482.

cvb's ckf schedules aVK; aVK loads myG/SU through buH.eG before buH.start and publishes fight/timeline UI globals. Thus12514 receives the actual current timeline, not an empty constructor timeline.

cvx's ckv applies ACTION phase and calls its private `a(cvx,byte)`; ACTION2 invokes eDT. eDT obtains bvY.dNG(), checks native ownership buH.bi(current) and active-turn ey(current.id), installs dbl.fcY input handling, then invokes buH.kz(current.id), which delegates ownership presentation to buJ.s. This is a concrete existing reconnect input producer.

cvn's cjv cancels pending animation recovery through aUb.Af, calls buH.dZ; dZ deserializes the fg/fcc envelope via fcb.eG/SU.a, then calls bvY.start. SU restore loads round, turn, status, deadline and current-slot member. SU.start only sets brX=true; bvY.start additionally releases camera blocking. bvY.dNG reads restored bhI/bhJ, resolving the current fighter from actual roster. cvn alone does not invoke the usual aUN turn-start presentation, but the preceding12514 has already restored owned control.

Do not add13482 merely to compensate for cvn lacking aUN. Original ckm/13482 schedules aUN, whose application invokes beS.be, changes timeline deadline, calls actual buH.bp turn-begin behavior, updates daT and may push btJ for the owned PC. That path is not a presentation-only snapshot; replay can introduce a second client turn lifecycle.13337 likewise schedules the native preturn action aVi. The current snapshot must preserve server FSM, ACK boundary, actual resources and retained runners instead.

Source dumps: `/tmp/wakemu-reconnect-{cjv,ckf,aVK,ckv,SU,bvY,fcc,ckm,aUN,cku}.txt`; targeted javap of installed client/lib/wakfu-client.jar. No production edits, tests, services or DB operations. Live acceptance remains separate; if input fails, inspect12514 eDT owner/current-clock guards rather than synthesizing turn events.
