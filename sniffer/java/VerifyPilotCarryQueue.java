import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

/** Original eWB/eZE logical owner relations, isolated from graphical parenting. */
public final class VerifyPilotCarryQueue {
    static final class Actor extends bjo {
        final Qf manager = new VerifyCombatReconstructionSlice.StateCollection();
        public Qf bax() { return manager; }
        Object logical(String name, Class<?> result, Class<?> parameter, Object argument) {
            try {
                // Invoke the original eGj implementation directly. big adds
                // renderer parenting/camera work after these same operations.
                var lookup = MethodHandles.privateLookupIn(big.class, MethodHandles.lookup());
                var type = parameter == null ? MethodType.methodType(result) : MethodType.methodType(result, parameter);
                var method = lookup.findSpecial(eGj.class, name, type, big.class).bindTo(this);
                return parameter == null ? method.invokeWithArguments() : method.invokeWithArguments(argument);
            } catch (Throwable error) { throw new IllegalStateException(error); }
        }
        public boolean a(eHH target) { return (boolean)logical("a",boolean.class,eHH.class,target); }
        public void a(eHG carrier) { logical("a",void.class,eHG.class,carrier); }
        public boolean Q(aBn target) { return (boolean)logical("R",boolean.class,aBn.class,target); }
        public boolean R(aBn target) { return (boolean)logical("R",boolean.class,aBn.class,target); }
        public void dda() { logical("dda",void.class,null,null); }
    }
    static final class Application extends aVo {
        final buQ world;
        final Map<Long,Actor> actors;
        boolean completed;
        Application(cvX packet, eZR runner, Map<Long,Actor> actors, PN context) {
            super(packet.cbc(),packet.eId(),packet.eII(),packet.bhe(),runner,packet.eIK());
            this.actors=actors;
            world=(buQ)Proxy.newProxyInstance(buQ.class.getClassLoader(),new Class[]{buQ.class},
                (p,m,a)->switch(m.getName()) {
                    case "bbg" -> context;
                    case "kq" -> actors.get((Long)a[0]);
                    case "equals" -> p==a[0];
                    default -> null;
                });
        }
        protected buQ cjD() { return world; }
        public big iA(long id) { return actors.get(id); }
        public long cby() { cYc(); return 0; }
        public void cbj() { super.cbj(); completed=true; }
    }
    static Actor actor(sun.misc.Unsafe unsafe,long id,int[] cell) throws Exception {
        Actor actor=new Actor(); actor.dA(id);
        var graphic=(VerifyPilotDisplacementQueue.Graphic)unsafe.allocateInstance(VerifyPilotDisplacementQueue.Graphic.class);
        VerifyCombatReconstructionSlice.set(graphic,"hPP",actor);
        VerifyCombatReconstructionSlice.set(graphic,"bkU",actor.bcy());
        VerifyCombatReconstructionSlice.set(actor,"hQB",graphic);
        actor.T(cell[0],cell[1],(short)cell[2]);
        return actor;
    }
    static Map<String,Object> view(Map<Long,Actor> actors) {
        var positions=new LinkedHashMap<Long,Object>();
        var relations=new LinkedHashMap<Long,Object>();
        actors.forEach((id,actor)-> {
            aBn cell=actor.baM();positions.put(id,new int[]{cell.getX(),cell.getY(),cell.bdn()});
            var relationship=new LinkedHashMap<String,Object>();
            relationship.put("carrier",actor.frz()==null?null:((PV)actor.frz()).Sn());
            relationship.put("carried",actor.fry()==null?null:((PV)actor.fry()).Sn());
            relations.put(id,relationship);
        });
        return Map.of("positions",positions,"relations",relations);
    }
    public static void main(String[] args) throws Exception {
        var unsafe=VerifyPilotDisplacementQueue.setup();
        apw.bGL().dd("jar:file:"+Path.of(args[11]).toAbsolutePath()+"/%d.jar!/%d.bin");
        bPS.elL();fyZ.guX().a(new bbV());
        long carrier=Long.parseLong(args[3]),carried=Long.parseLong(args[4]);
        int[] source={Integer.parseInt(args[5]),Integer.parseInt(args[6]),Integer.parseInt(args[7])};
        int[] target={Integer.parseInt(args[8]),Integer.parseInt(args[9]),Integer.parseInt(args[10])};
        Map<Long,Actor> actors=new LinkedHashMap<>();
        actors.put(carrier,actor(unsafe,carrier,source));actors.put(carried,actor(unsafe,carried,target));
        PW registry=(PW)Proxy.newProxyInstance(PW.class.getClassLoader(),new Class[]{PW.class},
            (p,m,a)->m.getName().equals("de")?actors.get((Long)a[0]):null);
        PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},
            (p,m,a)->switch(m.getName()) {
                case "bae" -> registry;
                case "bad", "baf", "baa" -> null;
                default -> m.invoke(bcz.dcW(),a);
            });
        var observations=new java.util.ArrayList<Object>();
        for(int index=0;index<2;index++) {
            cvX packet=new cvX();
            VerifyCombatReconstructionSlice.check(packet.dp(Files.readAllBytes(Path.of(args[index]))),"native carry packet decode");
            VerifyCombatReconstructionSlice.check(packet.eII()==(index==0?334:333),"owned carry then throw families");
            iN wire=iN.bf(packet.eIJ());
            eZR runner=(eZR)eVi.fLJ().pS(packet.eII()).b(context);
            VerifyCombatReconstructionSlice.check(runner.ds(packet.eIJ())!=null&&runner.baZ()!=null
                &&((eVn)runner.baZ()).aZE()==wire.Qs(),"exact native carry definition/hydration");
            var before=view(actors);
            Application action=new Application(packet,runner,actors,context);
            action.cYb();action.iD(wire.Qw());if(wire.Qx()) action.fe(wire.Qy());
            aER queue=new aER();queue.c(action);queue.cbu();
            VerifyCombatReconstructionSlice.check(action.completed&&queue.cbt().isEmpty(),"original carry cbj/FIFO");
            VerifyCombatReconstructionSlice.check(VerifyPilotDisplacementQueue.errors.get()==0,"native carry no swallowed error");
            var row=new LinkedHashMap<String,Object>();
            row.put("family",packet.eII());row.put("action_id",packet.cbc());row.put("uid",wire.LV());
            row.put("generic_effect",wire.Qs());row.put("caster",wire.Qw());
            row.put("before",before);row.put("after",view(actors));
            row.put("native_completed_action_ids",new int[]{packet.cbc()});row.put("queue_drained",true);
            observations.add(row);
            VerifyCombatReconstructionSlice.check(actors.get(carrier).frA()==(index==0)
                &&actors.get(carried).buX()==(index==0),"native reciprocal ownership transition");
        }
        Files.writeString(Path.of(args[2]),VerifyCombatReconstructionSlice.json(Map.of(
            "completed_normally",true,"stages",observations,
            "scope","original eWB/eZE/aVo.cbj/aER and eGj ownership/position methods; big renderer parenting and visual scripts skipped"))+"\n");
        System.out.println("PASS original native carry/throw logical ownership and callback queues");
        System.exit(0);
    }
}
