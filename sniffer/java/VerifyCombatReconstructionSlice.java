import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

/** Detached original-client oracle. Generates fixtures without server serializers.
 * Run against the original JAR only; the caller must bind all classpath hashes.
 * Actor/PN proxies provide identity and registry inputs, never packet decoding.
 */
public final class VerifyCombatReconstructionSlice {
    static final int FIGHT = 99;
    static final long CASTER = 22, TARGET = -33, STATE_UID = 2345, BASE_UID = 1234;
    static Path output;
    static final Map<String, Object> observations = new LinkedHashMap<>();

    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    static void set(Object object, String name, Object value) throws Exception {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try {
                Field field = type.getDeclaredField(name);
                field.setAccessible(true); field.set(object, value); return;
            } catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }

    static void save(String name, byte[] body) throws Exception {
        Files.write(output.resolve(name + ".bin"), body);
    }

    // Avoid the installed launcher's incompatible optional Jackson core/databind
    // pair. This writer formats observations only, never packet fixtures.
    static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof String string) return "\"" + string.replace("\\", "\\\\")
            .replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + "\"";
        if (value instanceof Map<?,?> map) {
            var entries = new java.util.ArrayList<String>();
            map.forEach((key,item) -> entries.add(json(key.toString()) + ":" + json(item)));
            return "{" + String.join(",",entries) + "}";
        }
        var items = new java.util.ArrayList<String>();
        if (value instanceof Iterable<?> values) for (Object item : values) items.add(json(item));
        else if (value.getClass().isArray()) {
            for (int index=0; index<java.lang.reflect.Array.getLength(value); index++)
                items.add(json(java.lang.reflect.Array.get(value,index)));
        } else throw new IllegalArgumentException("Unsupported observation type " + value.getClass());
        return "[" + String.join(",",items) + "]";
    }

    static ByteBuffer action(int size, int id) {
        return ByteBuffer.allocate(size).putInt(FIGHT).putInt(id).putInt(-1);
    }

    static byte[] effect(int opcode, int family, int action, byte[] proto, boolean immediate,
                         long target, long uid) {
        ByteBuffer bytes = action(18 + proto.length + (opcode == 12613 ? 1 : 0)
                + (opcode == 13560 ? 16 : 0), action);
        if (opcode == 12613) bytes.put((byte)(immediate ? 1 : 0));
        bytes.putInt(family).putShort((short)proto.length).put(proto);
        if (opcode == 13560) bytes.putLong(target).putLong(uid);
        return bytes.array();
    }

    static class StateCollection extends eZV { StateCollection() { super(null); } }

    static PV actor(long id, Qf registry) {
        return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(), new Class[]{PV.class},
            (proxy, method, args) -> switch (method.getName()) {
                case "Sn" -> id;
                case "bax" -> registry;
                case "bcz", "bcA" -> 0;
                case "bcB" -> (short)0;
                case "bav" -> (byte)0;
                case "bcy" -> aAS.dyA;
                case "toString" -> "FixtureActor" + id;
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }

    static class Complete extends aVo {
        final buQ world;
        Complete(eZR runner, PV caster, PV target) {
            super(8, -1, runner.d(), FIGHT, runner, false);
            PW actors = (PW)Proxy.newProxyInstance(PW.class.getClassLoader(), new Class[]{PW.class},
                (p, m, a) -> m.getName().equals("de")
                    ? ((Long)a[0] == caster.Sn() ? caster : (Long)a[0] == target.Sn() ? target : null)
                    : null);
            PN context = (PN)Proxy.newProxyInstance(PN.class.getClassLoader(), new Class[]{PN.class},
                (p, m, a) -> m.getName().equals("bae") ? actors : m.invoke(bcz.dcW(), a));
            world = (buQ)Proxy.newProxyInstance(buQ.class.getClassLoader(), new Class[]{buQ.class},
                (p, m, a) -> switch(m.getName()) {
                    case "bbg" -> context;
                    case "equals" -> p == a[0];
                    default -> null;
                });
        }
        protected buQ cjD() { return world; }
    }

    static class Observe extends aTR {
        Observe(eZR runner) { super(9, -1, FIGHT, runner.d(), runner); }
        void observe() { super.cbj(); }
    }

    static class Remove extends aVz {
        Remove(eZk runner, cvZ message) throws Exception {
            super(10, -1, FIGHT, 310, runner, message.eIL(), message.Qy(), message.eIJ());
            set(this, "hty", runner);
        }
        void remove() { super.cbj(); }
    }

    static eZk state(byte[] proto, PV caster, PV target) throws Exception {
        eZk runner = new eZk(); runner.lV(310); runner.a(bcz.dcW());
        check(runner.ds(proto) != null, "native state decode");
        set(runner, "bfr", caster); set(runner, "bfs", target);
        return runner;
    }

    static void bootstrap() throws Exception {
        byte[] fence = ByteBuffer.allocate(4).putInt(FIGHT).array();
        cvG flush = new cvG(); check(flush.dp(fence) && flush.bhe() == FIGHT,"native fence codec");
        save("13420",fence);
        // Native cvb reconnect mode avoids character snapshots; this proves roster
        // decoding, not native actor instantiation or presentation initialization.
        ByteBuffer body = ByteBuffer.allocate(100);
        body.putInt(FIGHT).put((byte)2).putLong(CASTER).putLong(0).putLong(0);
        body.putInt(0).putShort((short)0).putLong(0).putLong(0).put((byte)1).put((byte)2);
        body.putLong(CASTER).put((byte)0).put((byte)0).put((byte)0);
        body.putLong(TARGET).put((byte)1).put((byte)1).put((byte)0);
        body.put((byte)0).put((byte)0).put((byte)0).putInt(0);
        byte[] bytes = Arrays.copyOf(body.array(), body.position()); save("12847", bytes);
        cvb roster = new cvb(); check(roster.dp(bytes), "native roster decode");
        check(roster.bhe() == FIGHT && roster.eHa() == 2 && roster.Mj(0) == CASTER
            && roster.Mj(1) == TARGET && roster.eHx(), "native roster identities");
        observations.put("bootstrap", Map.of("fight_id", roster.bhe(), "actor_ids", roster.eHp(),
            "phase", roster.eHb(), "reconnect", roster.eHx(), "scope", "native_codec_roster"));
        bytes = ByteBuffer.allocate(43).putInt(FIGHT).putShort((short)2)
            .putLong(CASTER).putInt(2).putInt(-3).putShort((short)4)
            .putLong(TARGET).putInt(5).putInt(-3).putShort((short)4).put((byte)1).array();
        save("13652", bytes); cvq positions = new cvq(); boolean result = positions.dp(bytes);
        aBn own = positions.eHO().get(CASTER), other = positions.eHO().get(TARGET);
        check(!result && positions.eHO().size() == 2 && own.getX() == 2 && other.getX() == 5,
            "cvq populates despite returning false");
        observations.put("positions", Map.of("decode_return", result, "fight_id", positions.bhe(),
            "positions", new long[][]{{CASTER, own.getX(), own.getY(), own.bdn()},
                {TARGET, other.getX(), other.getY(), other.bdn()}}, "placement", positions.eHN()));
        amK nativePath = new amK(new int[][]{{2,-3,4},{3,-3,4},{4,-3,4}});
        byte[] route = nativePath.aqv();
        bytes = action(22 + route.length, 7).putLong(CASTER).put((byte)1).put((byte)0).put(route).array();
        save("13624", bytes); cvP movement = new cvP(); check(movement.dp(bytes), "native path decode");
        check(movement.OO() == CASTER && movement.bgl().equals(nativePath), "native path points");
        observations.put("movement", Map.of("fight_id", movement.bhe(), "action_id", movement.cbc(),
            "actor_id", movement.OO(), "movement_type", movement.eIC().name(),
            "points", movement.bgl().bDX(), "scope", "native_codec_path"));
        bytes = ByteBuffer.allocate(12).put((byte)0).put((byte)0).put((byte)1)
            .put((byte)1).putLong(TARGET).array(); save("12304", bytes);
        ctA removal = new ctA(); check(removal.dp(bytes), "native entity removal codec");
        check(removal.eFG().size() == 1 && removal.eFG().get(0).aIy() == TARGET, "removal identity");
        observations.put("entity_removal", Map.of("actor_id", TARGET, "type", removal.eFG().get(0).getFirst(),
            "first_flag", removal.eFH(), "second_flag", removal.eFI(),
            "scope", "codec_only; cgN delegates to buH.aY when actor.doI is nonnull; aY enqueues deferred world removal for fight termination dMe, not immediate fight unregister"));
    }

    static void states() throws Exception {
        PV caster = actor(CASTER, new StateCollection()); PV target = actor(TARGET, new StateCollection());
        int packed = fyW.ae((short)3442, (short)1);
        eZk original = eZk.a(null, caster, null, packed);
        check(original != null, "native state definition3442");
        original.f(target); original.dg(STATE_UID); original.dj(BASE_UID);
        iN proto = original.bca();
        // Explicit fixture removal gate, encoded by the installed native builder.
        proto = proto.QR().d(iB.Pr().c(proto.QH()).G(true).Py()).QX();
        byte[] bytes = effect(12613,310,8,proto.toByteArray(),false,TARGET,STATE_UID);
        save("12613-state310", bytes); cvX add = new cvX(); check(add.dp(bytes), "cvX native decode");
        check(!add.eIK() && add.eII() == 310, "cvX state nonimmediate");
        bytes = effect(13497,310,9,proto.toByteArray(),false,TARGET,STATE_UID);
        save("13497-state310",bytes); cvY observation = new cvY(); check(observation.dp(bytes), "cvY native decode");
        StateCollection observedRegistry = new StateCollection();
        eZk observed = state(observation.eIJ(), caster, actor(TARGET, observedRegistry));
        observed.bbq(); new Observe(observed).observe();
        check(observedRegistry.fSs().isEmpty(), "state observation must not register");
        StateCollection registry = new StateCollection(); target = actor(TARGET, registry);
        eZk installed = state(add.eIJ(), caster, target);
        Complete action = new Complete(installed, caster, target);
        action.cYb(); action.fe(TARGET); action.iD(CASTER);
        aER queue = new aER(); queue.c(action); queue.cbu();
        check(queue.cbt().isEmpty() && registry.fSs().size() == 1 && registry.dk(STATE_UID) == installed,
            "native queue retained state");
        check(!installed.bbs() && installed.fMV(), "native gameplay disabled/removal gate");
        bytes = effect(13560,310,10,proto.toByteArray(),false,TARGET,STATE_UID);
        save("13560-state310",bytes); cvZ remove = new cvZ(); check(remove.dp(bytes), "cvZ native decode");
        new Remove(installed, remove).remove();
        check(registry.dk(STATE_UID) == null && registry.fSs().isEmpty(), "native owned state removal");
        observations.put("state310", Map.of("uid", proto.LV(), "base_uid", proto.Qq(),
            "generic_effect", proto.Qs(), "caster_id", proto.Qw(), "target_id", proto.Qy(),
            "packed_value", proto.getValue(), "state_reference", 3442, "state_level", 1,
            "additional", Map.of("uid", proto.QA().LV(), "packed_value", proto.QA().getValue()),
            "native_outcomes", Map.of("observation_registrations", 0, "completion_registrations",1,
                "queue_drained",true,"removal_remaining",0,"removal_gate",true)));
    }

    static class Areas extends Qs { public Qq dp(long uid) { return null; } }
    static class AreaRunner extends eYQ {
        void create() { super.c(null, false); }
    }

    static final class Grid extends QI {
        Grid() {
            bpZ = 0; bqa = -8; bqd = 16; bqe = 16;
            biD = new short[256]; biE = 256;
        }
    }

    static final class Occupant implements java.lang.reflect.InvocationHandler {
        byte slot = -1;
        int x, y;
        final long id;
        Occupant(long id, int x, int y) { this.id=id; this.x=x; this.y=y; }
        QK actor() {
            return (QK)Proxy.newProxyInstance(QK.class.getClassLoader(),new Class[]{QK.class},this);
        }
        public Object invoke(Object actor, java.lang.reflect.Method method, Object[] args) {
            return switch(method.getName()) {
                case "M" -> { slot=(Byte)args[0]; yield null; }
                case "bcN" -> slot;
                case "bcO", "bcP", "bcQ" -> true;
                case "bcz" -> x;
                case "bcA" -> y;
                case "bcL", "bcK" -> (byte)0;
                case "equals" -> actor == args[0];
                case "hashCode" -> System.identityHashCode(actor);
                case "toString" -> "FixtureOccupant"+id;
                default -> throw new UnsupportedOperationException(method.getName());
            };
        }
    }

    static void membership() throws Exception {
        cvb roster = new cvb(); roster.dp(Files.readAllBytes(output.resolve("12847.bin")));
        cvq positions = new cvq(); positions.dp(Files.readAllBytes(output.resolve("13652.bin")));
        fdt<bjo> registry = new fdt<>();
        bjo caster = new bjo(), target = new bjo();
        caster.dA(roster.Mj(0)); target.dA(roster.Mj(1));
        aBn first = positions.eHO().get(caster.Sn()), second = positions.eHO().get(target.Sn());
        // efR exposes the original logical coordinate object. Hydrate it with
        // its native setter; big.a additionally creates graphics resources.
        caster.efR().Q(first.getX(),first.getY(),first.bdn());
        target.efR().Q(second.getX(),second.getY(),second.bdn());
        registry.a(caster,roster.Mk(0),true,caster);
        registry.a(target,roster.Mk(1),true,target);
        check(registry.ry(CASTER)==caster && registry.ry(TARGET)==target,"native fdt membership birth");
        cvP movement = new cvP(); movement.dp(Files.readAllBytes(output.resolve("13624.bin")));
        int[] end = movement.bgl().bDW();
        caster.efR().Q(end[0],end[1],(short)end[2]);
        check(caster.bcz()==4 && caster.bcA()==-3 && caster.bcB()==4,"native actor position update");
        registry.bx(target);
        check(registry.ry(TARGET)==null && registry.ry(CASTER)==caster,"native fdt targeted unregister");
        Grid grid = new Grid();
        Occupant own = new Occupant(CASTER,first.getX(),first.getY());
        Occupant other = new Occupant(TARGET,second.getX(),second.getY());
        QK ownActor=own.actor(), otherActor=other.actor();
        grid.f(ownActor); grid.f(otherActor);
        byte ownSlot=own.slot, otherSlot=other.slot;
        check(grid.O(ownSlot)==ownActor && grid.O(otherSlot)==otherActor
            && grid.g(2,-3,(short)4) && grid.g(5,-3,(short)4),"native QI birth and occupancy");
        grid.g(ownActor); own.x=end[0]; own.y=end[1]; grid.f(ownActor);
        check(!grid.g(2,-3,(short)4) && grid.g(4,-3,(short)4),"native QI position occupancy update");
        grid.g(otherActor);
        check(grid.O(otherSlot)==null && !grid.g(5,-3,(short)4)
            && grid.O(own.slot)==ownActor && grid.g(4,-3,(short)4),"native QI targeted cleanup");
        observations.put("membership_primitives",Map.of("created_actor_ids",new long[]{CASTER,TARGET},
            "remaining_actor_ids",new long[]{CASTER},"actor_final_position",end,
            "native_registry","fdt.a/fdt.bx with real bjo objects",
            "native_occupancy","QI.f/QI.g with explicit blocking QK fixture inputs",
            "scope","native primitives driven by decoded identities/positions; fdt.bx is not asserted as a ctA consumer; ctA live-fight handling defers world removal until buH.dMe"));
        byte[] terminalBytes = action(32,13).put((byte)0).put((byte)1).putLong(CASTER)
            .put((byte)1).putLong(TARGET).put((byte)0).array();
        save("12238",terminalBytes);
        cvF terminal = new cvF(); check(terminal.dp(terminalBytes),"native fight termination codec");
        check(terminal.bhe()==FIGHT && !terminal.eIn() && terminal.eIk().equals(java.util.List.of(CASTER))
            && terminal.eIl().equals(java.util.List.of(TARGET)) && terminal.eIm().isEmpty(),"native terminal lists");
        registry.clear();
        check(registry.ry(CASTER)==null && registry.ry(TARGET)==null,"native terminal registry clear");
        observations.put("terminal",Map.of("fight_id",terminal.bhe(),"action_id",terminal.cbc(),
            "flag",terminal.eIn(),"first_list",terminal.eIk(),"second_list",terminal.eIl(),
            "third_list",terminal.eIm(),"native_registry_remaining",registry.fVf().size(),
            "consumer_path","ckc.a -> aUH.cXi normal branch -> buH.ciq -> fbX.ciq -> fcb.ciq -> fcb.dLN -> fdt.clear",
            "scope","original codec and final native fdt.clear primitive executed; full graphics-consuming terminal action not executed; terminal completion requires separate trusted witness"));
    }

    static faV prototype(int reference) {
        final faV[] found = {null};
        apw.bGL().a(new aKa(), new apB<aKa>() {
            public void load(aKa data) { if (data.d() == reference) found[0] = bcN.hFx.a(data); }
        });
        check(found[0] != null, "native area prototype"); return found[0];
    }

    static void areas() throws Exception {
        eGM.a(null); faV prototype = prototype(1474);
        fbr.fTN().e(prototype);
        Map<String,Object> matrix = new LinkedHashMap<>();
        for (boolean keep : new boolean[]{false,true}) for (boolean retained : new boolean[]{false,true}) {
            long uid = 7001 + (keep ? 2 : 0) + (retained ? 1 : 0);
            Areas manager = new Areas();
            AreaRunner original = new AreaRunner();
            set(original,"rGF",uid); set(original,"rGR",(short)1); set(original,"rGS",keep);
            set(original,"aSg",1474); original.dg(8000+uid); original.dj(BASE_UID);
            set(original,"bfr",actor(CASTER,new StateCollection())); set(original,"bft",new aBn(2,-3,(short)4));
            iN proto = original.bca();
            proto = proto.QR().d(iB.Pr().c(proto.QH()).G(true).Py()).QX();
            // Rehydrate native additional bytes, then exercise the original area
            // callback against the original Qs registry and actual native area.
            AreaRunner decoded = new AreaRunner(); decoded.lV(315);
            check(decoded.ds(proto.toByteArray()) != null && decoded.RD() == uid, "native area decode UID");
            // Ty is a native retention predicate, NOT the serialized execution
            // flag iB.MB. Supply native default definition and explicit fixture
            // retention suppression independently of the wire execution flag.
            set(decoded,"bfp",eVJ.fMh()); set(decoded,"bfM",!retained);
            check(decoded.Ty() == retained,"native area retention predicate");
            set(decoded,"bfr",actor(CASTER,new StateCollection()));
            set(decoded,"bfw",Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},
                (p,m,a) -> m.getName().equals("baf") ? manager : null));
            // The original consumer constructs a real native prototype instance
            // directly from the decoded position/value/additional data.
            decoded.create();
            check(manager.bdl() == 1 && manager.dn(uid) == decoded.fkS(),"native decoded area creation");
            check(decoded.fkS().bct() == 1474 && decoded.fkS().bcz() == 2
                && decoded.fkS().bcA() == -3,"native decoded area identity and position");
            byte[] addBytes = effect(12613,315,11,proto.toByteArray(),false,0,decoded.LV());
            String suffix = "area315-keep"+(keep?1:0)+"-retained"+(retained?1:0);
            save("12613-"+suffix,addBytes); cvX add = new cvX(); check(add.dp(addBytes),"native area wrapper");
            byte[] removeBytes = effect(13560,315,12,proto.toByteArray(),false,CASTER,decoded.LV());
            save("13560-"+suffix,removeBytes); cvZ remove = new cvZ(); check(remove.dp(removeBytes),"native area removal wrapper");
            decoded.bbR(); boolean removed = manager.dn(uid) == null;
            check(removed == (!keep && retained), "native area keep/retained removal");
            matrix.put(suffix,Map.of("uid",proto.LV(),"base_uid",proto.Qq(),"generic_effect",proto.Qs(),
                "caster_id",proto.Qw(),"area_uid",proto.QA().Mk(),"prototype",proto.getValue(),
                "keep",proto.QA().Mc(),"retained",retained,"native_remaining",manager.bdl()));
        }
        observations.put("area315",matrix);
        observations.put("area_scope","original eYQ native decoded creation and bbR/Qs removal; native default definition and bfM retention suppression supplied as fixture inputs; Ty retention is independent from iB.MB execution; creation calls protected native c directly, not aVo queue");
    }

    public static void main(String[] args) throws Exception {
        output = Path.of(args[0]); Files.createDirectories(output);
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        fyZ.guX().a(new bbV());
        bootstrap(); states(); areas(); membership();
        observations.put("completed_normally",true);
        Files.writeString(output.resolve("observations.json"),json(observations)+"\n");
        System.out.println("PASS original native reconstruction slice; observations.json and independently generated fixtures");
    }
}
