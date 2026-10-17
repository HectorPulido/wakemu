import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

/** Actual native retained state/area registration and owned callback retirement. */
public final class VerifyPilotAreaQueue {
    static final class Application extends aVo {
        final buQ world;
        boolean completed;
        Application(cvX packet,eZR runner,PN context) {
            super(packet.cbc(),packet.eId(),packet.eII(),packet.bhe(),runner,packet.eIK());
            world=(buQ)Proxy.newProxyInstance(buQ.class.getClassLoader(),new Class[]{buQ.class},
                (p,m,a)->switch(m.getName()) {
                    case "bbg" -> context;
                    case "equals" -> p==a[0];
                    default -> null;
                });
        }
        protected buQ cjD() { return world; }
        public long cby() { cYc(); return 0; }
        public void cbj() { super.cbj(); completed=true; }
    }
    static final class Removal extends aVz {
        boolean completed;
        Removal(cvZ packet,eZR runner) throws Exception {
            super(packet.cbc(),packet.eId(),packet.bhe(),packet.eII(),runner,
                  packet.eIL(),packet.Qy(),packet.eIJ());
            VerifyCombatReconstructionSlice.set(this,"hty",runner);
        }
        public long cby() { return 0; }
        protected void cbj() { super.cbj(); completed=true; }
    }
    static Map<String,Object> view(Map<Long,VerifyCombatReconstructionSlice.StateCollection> managers,
                                  VerifyCombatReconstructionSlice.Areas areas) {
        var stateRows=new LinkedHashMap<Long,Object>();
        managers.forEach((owner,manager)-> {
            for(Qe entry:manager.fSs()) {
                if(entry instanceof eZk state) stateRows.put(state.LV(),Map.of(
                    "state_id",state.fQW().guI(),"level",state.fQW().cmZ(),"owner",owner));
            }
        });
        var areaRows=new LinkedHashMap<Long,Object>();
        for(Qq area:areas.bdm()) {
            areaRows.put(area.Sn(),Map.of("prototype",((faV)area).bct(),
                "cell",new int[]{area.bcz(),area.bcA(),area.bcB()}));
            if(area.bax()!=null) for(Qe entry:area.bax()) {
                if(entry instanceof eZk state) stateRows.put(state.LV(),Map.of(
                    "state_id",state.fQW().guI(),"level",state.fQW().cmZ(),"owner",area.Sn()));
            }
        }
        return Map.of("states",stateRows,"areas",areaRows);
    }
    public static void main(String[] args) throws Exception {
        var unsafe=VerifyPilotDisplacementQueue.setup();
        Path directory=Path.of(args[0]);
        apw.bGL().dd("jar:file:"+Path.of(args[2]).toAbsolutePath()+"/%d.jar!/%d.bin");
        bPS.elL();fyZ.guX().a(new bbV());eGM.a(null);
        var actors=new LinkedHashMap<Long,PV>();
        var managers=new LinkedHashMap<Long,VerifyCombatReconstructionSlice.StateCollection>();
        var areas=new VerifyCombatReconstructionSlice.Areas();
        var areaIds=new java.util.HashSet<Long>();
        for(String line:Files.readAllLines(directory.resolve("stream.txt"))) {
            String[] fields=line.split(" ");
            if(Integer.parseInt(fields[0])==12613) {
                cvX message=new cvX();message.dp(Files.readAllBytes(directory.resolve(fields[1])));
                if(message.eII()==308||message.eII()==315) areaIds.add(iN.bf(message.eIJ()).QA().Mk());
            }
        }
        PW registry=(PW)Proxy.newProxyInstance(PW.class.getClassLoader(),new Class[]{PW.class},
            (p,m,a)->m.getName().equals("de")?
                (areas.dn((Long)a[0])!=null?areas.dn((Long)a[0]):actors.get((Long)a[0])):null);
        PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},
            (p,m,a)->switch(m.getName()) {
                case "bae" -> registry;
                case "baf" -> areas;
                case "bad", "baa" -> null;
                default -> m.invoke(bcz.dcW(),a);
            });
        var retained=new LinkedHashMap<Long,eZR>();
        var observations=new java.util.ArrayList<Object>();
        for(String line:Files.readAllLines(directory.resolve("stream.txt"))) {
            String[] row=line.split(" ");int opcode=Integer.parseInt(row[0]);
            byte[] body=Files.readAllBytes(directory.resolve(row[1]));
            int family,actionId;byte[] proto;cvX add=null;cvZ remove=null;
            if(opcode==12613) {
                add=new cvX();VerifyCombatReconstructionSlice.check(add.dp(body),"native application envelope");
                family=add.eII();proto=add.eIJ();actionId=add.cbc();
            } else if(opcode==13560) {
                remove=new cvZ();VerifyCombatReconstructionSlice.check(remove.dp(body),"native removal envelope");
                family=remove.eII();proto=remove.eIJ();actionId=remove.cbc();
            } else throw new AssertionError("Unsupported retained lifecycle opcode");
            VerifyCombatReconstructionSlice.check(family==310||family==315||family==308,"bounded retained lifecycle family");
            iN wire=iN.bf(proto);
            for(long id:new long[]{wire.Qw(),wire.Qx()?wire.Qy():wire.Qw()}) {
                if(!actors.containsKey(id)&&!areaIds.contains(id)) {
                    var actor=VerifyPilotDisplacementQueue.actor(unsafe,id,new int[]{0,0,0});
                    managers.put(id,(VerifyCombatReconstructionSlice.StateCollection)actor.manager);
                    actors.put(id,actor);
                }
            }
            if(family==315||family==308) fbr.fTN().e(VerifyCombatReconstructionSlice.prototype(wire.getValue()));
            eZR decoded=(eZR)eVi.fLJ().pS(family).b(context);
            VerifyCombatReconstructionSlice.check(decoded.ds(proto)!=null,"exact native retained payload hydration");
            var before=view(managers,areas);
            var observation=new LinkedHashMap<String,Object>();
            observation.put("opcode",opcode);observation.put("family",family);observation.put("action_id",actionId);
            observation.put("uid",decoded.LV());observation.put("generic_effect",wire.Qs());
            observation.put("retained",decoded.Ty());
            observation.put("observation_registers",(decoded.Ty()||decoded.bbW())&&(decoded.aZN()||decoded.bbW()));
            aER queue=new aER();
            if(add!=null) {
                Application action=new Application(add,decoded,context);action.cYb();action.iD(wire.Qw());
                if(wire.Qx()) action.fe(wire.Qy());queue.c(action);queue.cbu();
                VerifyCombatReconstructionSlice.check(action.completed,"original retained application callback");
                if(decoded.Ty()) retained.put(decoded.LV(),decoded);
            } else {
                eZR runner=retained.get(decoded.LV());
                VerifyCombatReconstructionSlice.check(runner!=null,"removal references exact retained native runner");
                VerifyCombatReconstructionSlice.check(runner.ds(proto)!=null,"native retained removal hydration");
                runner.a(context);
                VerifyCombatReconstructionSlice.set(runner,"bfr",registry.de(wire.Qw()));
                if(wire.Qx()) VerifyCombatReconstructionSlice.set(runner,"bfs",registry.de(wire.Qy()));
                Removal action=new Removal(remove,runner);queue.c(action);queue.cbu();
                VerifyCombatReconstructionSlice.check(action.completed,"original owned removal callback");
                retained.remove(decoded.LV());
            }
            VerifyCombatReconstructionSlice.check(queue.cbt().isEmpty(),"original retained callback FIFO drained");
            VerifyCombatReconstructionSlice.check(VerifyPilotDisplacementQueue.errors.get()==0,"no swallowed native retained execution error");
            observation.put("before",before);observation.put("after",view(managers,areas));
            observation.put("native_completed_action_ids",new int[]{actionId});observation.put("queue_drained",true);
            observations.add(observation);
        }
        Files.writeString(Path.of(args[1]),VerifyCombatReconstructionSlice.json(Map.of(
            "completed_normally",true,"stages",observations,"final",view(managers,areas),
            "scope","original native definitions, aVo/aVz callbacks, Qf/Qs retained ownership; visual script/wait/renderer lookup skipped"))+"\n");
        System.out.println("PASS original native retained area/state callbacks and ownership");
        System.exit(0);
    }
}
