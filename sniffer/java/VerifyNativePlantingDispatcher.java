import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.nio.file.Path;
import java.lang.reflect.Field;

/** Offline integration of unmodified installed world packet dispatch. */
public final class VerifyNativePlantingDispatcher {
    static Object field(Object owner, String name) throws Exception {
        for (Class<?> type = owner.getClass(); type != null; type = type.getSuperclass()) {
            try { Field f = type.getDeclaredField(name); f.setAccessible(true); return f.get(owner); }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    static void set(Object owner, String name, Object value) throws Exception {
        for (Class<?> type = owner.getClass(); type != null; type = type.getSuperclass()) {
            try { Field f = type.getDeclaredField(name); f.setAccessible(true); f.set(owner, value); return; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    static void prepareDisplay(biB actor, int profession) throws Exception {
        set(aTx.cWt(), "hsi", actor);
        actor.dtz().lr(true);
        bJp[] seed = new bJp[1];
        apw.bGL().a(new aLO(), new apB<aLO>() { public void load(aLO raw) {
            bJp item = new bIJ().f(raw);
            if (item.gfJ() instanceof bIi action && action.cmG() == profession
                && (seed[0] == null || item.d() < seed[0].d())) seed[0] = item;
        }});
        if (seed[0] == null) throw new AssertionError("native seed missing");
        bIi action = (bIi) seed[0].gfJ();
        fnR item = fnR.a(123L, seed[0]);
        // A real one-pixel native texture satisfies highlight initialization; no rendering occurs.
        set(afw.bzi(), "bVh", avT.bPG().a(aqP.cTq.bII(), 123L, 1, 1, false));
        set(dev.fia(), "iyp", item);
        short[] family = new short[1];
        apw.bGL().a(new aNl(), new apB<aNl>() { public void load(aNl raw) {
            if (raw.d() == action.dJb()) family[0] = (short) raw.aeV();
        }});
        if (family[0] == 0) throw new AssertionError("Missing native resource family");
        bOk resource = new bOk(action.dJb(), family[0], (short)0, (short)0, fyb.ttn, false,
            (short)0, java.util.Map.of(), 0, false);
        bOl.eiQ().a(resource);
        ffY ground = new ffY(123);
        java.util.HashMap<Integer,Short> thresholds = new java.util.HashMap<>();
        thresholds.put(action.dJb(), (short)40);
        ground.e(thresholds); ffX.fZV().a(ground);
        short[] cells = new short[324]; java.util.Arrays.fill(cells, (short)123);
        aIl map = new aIl(); map.a(eFn.fpF().k(cells));
        ack.buz().fs(1L); ack.buz().a((short)0, (short)0, map);
        VF.fs(1L); VF.a(1L, (short)0, (short)0, (short)0, new VJ());
        System.out.println("Display seed=" + seed[0].d() + " resource=" + action.dJb()
            + " soil=" + map.U(0,0,0));
    }
    static int displayed() throws Exception {
        java.lang.reflect.Method method = dev.class.getDeclaredMethod("am", aBn.class);
        method.setAccessible(true);
        return (int) method.invoke(dev.fia(), new aBn(0,0,(short)0));
    }
    @SuppressWarnings("unchecked")
    static void run(String[] args) throws Exception {
        if (args.length != 4) throw new IllegalArgumentException("Expected positive, negative, restore and reapply production framed batch paths");
        org.apache.log4j.BasicConfigurator.configure();
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        cvX event = firstEffect(args[0]);
        iN proto = iN.bf(event.eIJ());
        biB actor = new biB(false);
        actor.dA(proto.Qy());
        // Registration hooks create an OpenGL scene; seed the real registry for this offline fixture.
        ((gnu.trove.map.hash.TLongObjectHashMap<big>) field(bio.dpx(), "ihk")).put(actor.Sn(), actor);
        bcA.dcX().AH(72217);
        if (bio.dpx().de(proto.Qy()) != actor) throw new AssertionError("native registry identity");
        prepareDisplay(actor, proto.QA().Mg());
        check(actor, proto.QA().Mg(), 0, 40, "baseline");
        dispatchBatch(args[0], actor);
        check(actor, proto.QA().Mg(), 25, 50, "positive");
        cvX negative = firstEffect(args[1]);
        if (iN.bf(negative.eIJ()).getValue() != -25) throw new AssertionError("negative fixture");
        dispatchBatch(args[1], actor);
        check(actor, proto.QA().Mg(), 0, 40, "negative");
        dispatchBatch(args[2], actor);
        check(actor, proto.QA().Mg(), 25, 50, "before reset");
        actor.drJ().a(new byte[] {0,0}, bcz.dcW());
        check(actor, proto.QA().Mg(), 0, 40, "native snapshot reset");
        dispatchBatch(args[3], actor);
        check(actor, proto.QA().Mg(), 25, 50, "reapply after reset");
        verifyGarden(actor, proto.QA().Mg());
        System.out.println("PASS installed cjj/cjK/aVo/aER/bio/biB/dev.am integration: positive, negative, native reset, reapply and native garden ground28");
    }
    record Frame(int opcode, byte[] body) { }
    static List<Frame> frames(String path) throws Exception {
        ByteBuffer input = ByteBuffer.wrap(Files.readAllBytes(Path.of(path)));
        List<Frame> frames = new ArrayList<>();
        while (input.hasRemaining()) {
            if (input.remaining() < 6) throw new AssertionError("truncated native frame");
            int length = input.getInt(); int opcode = Short.toUnsignedInt(input.getShort());
            if (length < 6 || length - 6 > input.remaining()) throw new AssertionError("invalid native frame length");
            byte[] body = new byte[length - 6]; input.get(body); frames.add(new Frame(opcode, body));
        }
        if (frames.size() < 2 || frames.get(frames.size() - 1).opcode() != 13420)
            throw new AssertionError("production publication missing final13420 flush");
        return frames;
    }
    static cvX firstEffect(String path) throws Exception {
        Frame frame = frames(path).get(0);
        cvX event = new cvX();
        if (frame.opcode() != 12613 || !event.dp(frame.body())) throw new AssertionError("packet decode");
        return event;
    }
    static void check(biB actor, int profession, int bonus, int display, String phase) throws Exception {
        int actualBonus = actor.dpX().a(eRJ.raN, profession, 2);
        int actualDisplay = displayed();
        if (actor.dpX().a(eRJ.raN, profession + 1, 2) != 0)
            throw new AssertionError("Unrelated profession changed");
        if (actualBonus != bonus || actualDisplay != display)
            throw new AssertionError(phase + ": bonus=" + actualBonus + " display=" + actualDisplay);
        System.out.println("PASS " + phase + " modifier=" + actualBonus + " actual dev.am=" + actualDisplay);
    }
    static void dispatchBatch(String path, biB actor) throws Exception {
        List<Frame> frames = frames(path);
        List<aVo> actions = new ArrayList<>();
        int profession = iN.bf(firstEffect(path).eIJ()).QA().Mg();
        int before = actor.dpX().a(eRJ.raN, profession, 2);
        int delta = 0;
        for (int index = 0; index < frames.size(); index++) {
            Frame frame = frames.get(index);
            if (index == frames.size() - 1) {
                cvG flush = new cvG();
                if (frame.opcode() != 13420 || !flush.dp(frame.body()) || flush.bhe() != -1
                    || cjj.eDF().b(flush)) throw new AssertionError("native production world queue flush");
                continue;
            }
            cvX event = new cvX();
            if (frame.opcode() != 12613 || !event.dp(frame.body())) throw new AssertionError("unexpected publication frame");
            iN proto = iN.bf(event.eIJ());
            if (event.bhe() != -1 || event.eIK() || event.eII() != 2000 || proto.QA().Mg() != profession
                || proto.Qy() != actor.Sn() || proto.Qw() != actor.Sn() || proto.Qs() != 72217)
                throw new AssertionError("production carrier contract");
            delta += proto.getValue();
            if (cjj.eDF().b(event)) throw new AssertionError("native dispatcher did not handle event");
            aER manager = (aER) ((gnu.trove.map.hash.TIntObjectHashMap<?>) field(aUb.cXs(), "htU")).get(-1);
            if (manager == null) throw new AssertionError("dispatcher did not enqueue");
            aEO queue = (aEO) field(manager, "dIH");
            if (queue == null || queue.cbn().size() != index + 1
                || !(queue.cbn().get(index) instanceof aVo)) throw new AssertionError("missing actual aVo");
            actions.add((aVo) queue.cbn().get(index));
            if (actor.dpX().a(eRJ.raN, profession, 2) != before)
                throw new AssertionError("12613 unexpectedly bypassed native queue");
        }
        if (actor.dpX().a(eRJ.raN, profession, 2) != before + delta)
            throw new AssertionError("production flush did not apply entire batch");
        for (aVo action : actions)
            if (action.cYi().bbb() != actor) throw new AssertionError("actual native target resolution");
    }
    static void verifyGarden(biB actor, int profession) throws Exception {
        apw.bGL().a(new aLp(), new apB<aLp>() { public void load(aLp raw) {
            if (raw.d() != 28) return;
            ffY ground = new ffY(28); ground.e(raw.coi()); ground.f(raw.coj());
            ffX.fZV().a(ground);
        }});
        short[] cells = new short[324]; java.util.Arrays.fill(cells, (short)28);
        aIl map = (aIl) ack.buz().bu(0,0); map.a(eFn.fpF().k(cells));
        int withBonus = displayed();
        actor.drJ().a(new byte[] {0,0}, bcz.dcW());
        int baseline = displayed();
        if (baseline <= 0 || withBonus != Math.min(100, Math.round(baseline * 1.25f)))
            throw new AssertionError("native garden display " + baseline + " -> " + withBonus);
        System.out.println("PASS native garden ground28 actual dev.am=" + baseline + " -> " + withBonus);
        actor.dtz().lr(false);
        if (displayed() != -1) throw new AssertionError("Native subscription restriction bypassed");
        actor.dtz().lr(true);
        java.util.Arrays.fill(cells, (short)0); map.a(eFn.fpF().k(cells));
        if (displayed() != -1) throw new AssertionError("Native empty ground restriction bypassed");
        System.out.println("PASS actual dev.am preserves subscription and zero-ground restrictions");
    }
    public static void main(String[] args) {
        try { run(args); System.exit(0); }
        catch (Throwable failure) { failure.printStackTrace(); System.exit(1); }
    }
}
