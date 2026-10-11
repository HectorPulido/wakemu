import java.io.PrintWriter;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.lang.reflect.Field;
import java.util.HashMap;

/** Offline oracle: native soil/climate/bonus arithmetic and raw effect carrier. */
public final class VerifyNativePlantingPolicy {
    static class Actor extends eGj {public eGj dpu(){return null;} public boolean dnz(){return false;} Qf effects; public Qf bax(){return effects;} public fcb dpt(){return null;} public void a(PE a0, PG a1){return;} public void a(QM a0){return;} public PA b(PC a0){return null;} short level; public short cmZ(){return level;} public long jy(long a0){return 0;}public eGA dnv(){return null;}public java.util.Collection<? extends eGj> dnC(){return null;}public eGj jt(long a0){return null;}public foA dnK(){return null;}public fnw dps(){return null;}public long dpS(){return 0;}public eHd dpT(){return null;}public void dpQ(){return;}public boolean dpR(){return false;}protected frj dnJ(){return null;}public void Dg(int a0){return;}public long jx(long a0){return 0;}public eGj b(long a0, aBn a1, short a2, eHD a3, SQ a4, boolean a5, eHN<ffe> a6){return null;}protected eGH dpU(){return null;}protected byte dpV(){return 0;}public void dnO(){return;}public float dpW(){return 0;}eRN modifiers; public eRL dpX(){return modifiers;}public void aQc(){return;}public int doX(){return 0;}public int doY(){return 0;}public void c(int a0, java.lang.Object a1){return;}public eGj dpr(){return null;}}
    static class WorldApplication extends aVo {
        WorldApplication(eZR runner) { super(1, 0, 2000, -1, runner, false); }
        void complete() { super.cbj(); }
    }
    public static void main(String[] args) throws Exception {
        fyb climate = fyb.ttn;
        Vl incompatible = null;
        for (Vl weather : Vl.values()) {
            if (weather != Vl.bKu && !climate.gsO().contains(weather)) {
                incompatible = weather;
                break;
            }
        }
        if (incompatible == null) throw new AssertionError("Missing incompatible native weather");
        fxX<fxZ> resource = new fxX<>(123456, (short) 19, (short) 0, (short) 0, climate, false);
        int count = 0;
        try (PrintWriter output = new PrintWriter(args[0])) {
            output.println("terrain,compatible,bonus,probability,displayed");
            for (int terrain = 0; terrain <= 100; terrain++) {
                ffY ground = new ffY(123);
                HashMap<Integer, Short> thresholds = new HashMap<>();
                thresholds.put(123456, (short) terrain);
                ground.e(thresholds);
                for (int bonus = -100; bonus <= 200; bonus++) {
                    eRN modifiers = new eRN();
                    modifiers.a(eRJ.raN, 72, 2, bonus);
                    fyh actor = profession -> (double) ((float) modifiers.a(eRJ.raN, profession, 2) / 100.0f);
                    for (boolean compatible : new boolean[] {true, false}) {
                        double probability = fyi.b(actor, resource, ground, compatible ? Vl.bKu : incompatible, 72);
                        int displayed = probability <= 0 ? -1 : (int) Math.round(probability * 100);
                        output.println(terrain + "," + compatible + "," + bonus + "," + Double.toString(probability) + "," + displayed);
                        count++;
                    }
                }
            }
        }
        if (args.length > 1) {
            sa section = new sa();
            apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
            ByteBuffer sectionBytes = ByteBuffer.wrap(Files.readAllBytes(Path.of(args[1])));
            if (!section.aG(sectionBytes) || sectionBytes.hasRemaining() || section.Ym == null || section.Yn != null)
                throw new AssertionError("Invalid native raw running-effect section");
            ByteBuffer raw = ByteBuffer.wrap(section.Ym.TM);
            Field unsafeField = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
            unsafeField.setAccessible(true);
            sun.misc.Unsafe unsafe = (sun.misc.Unsafe) unsafeField.get(null);
            Actor actor = (Actor) unsafe.allocateInstance(Actor.class);
            actor.modifiers = new eRN();
            actor.effects = new eZV(actor);
            int effects = raw.getShort();
            for (int i = 0; i < effects; i++) {
                if (raw.getInt() != 2000) throw new AssertionError("Unexpected effect class");
                byte[] payload = new byte[raw.getShort()];
                raw.get(payload);
                eXx effect = new eXx(eRJ.raN, 2);
                effect.a(bcz.dcW());
                iN proto = effect.ds(payload);
                if (proto == null || proto.QA().Mg() <= 0)
                    throw new AssertionError("Native bonus amount/profession did not decode");
                Field profession = eXx.class.getDeclaredField("kdm");
                profession.setAccessible(true);
                if (profession.getInt(effect) != proto.QA().Mg())
                    throw new AssertionError("Native additional field19 did not restore profession");
                Field target = Qe.class.getDeclaredField("bfs");
                target.setAccessible(true);
                target.set(effect, actor);
                int amount = proto.getValue();
                new WorldApplication(effect).complete();
                if (actor.modifiers.a(eRJ.raN, proto.QA().Mg(), 2) != amount)
                    throw new AssertionError("Native world effect did not apply to profession modifier");
                eXx negative = new eXx(eRJ.raN, 2);
                negative.a(bcz.dcW()); negative.ds(payload); negative.dg(proto.LV() + 1000); negative.ow(-amount);
                target.set(negative, actor);
                new WorldApplication(negative).complete();
                if (actor.modifiers.a(eRJ.raN, proto.QA().Mg(), 2) != 0)
                    throw new AssertionError("Negative world delta did not restore modifier");
                eXx restored = new eXx(eRJ.raN, 2);
                restored.a(bcz.dcW()); restored.ds(payload); restored.dg(proto.LV() + 2000); target.set(restored, actor);
                new WorldApplication(restored).complete();
                actor.effects.clear();
                if (actor.modifiers.a(eRJ.raN, proto.QA().Mg(), 2) != 0)
                    throw new AssertionError("Native runner-manager clear did not restore modifier");
                if (raw.getInt() != 0) throw new AssertionError("Unexpected expiry");
            }
            if (raw.hasRemaining()) throw new AssertionError("Trailing native effect bytes");
            System.out.println("PASS native raw snapshot decoder " + effects + " effects, amount/profession via original aVo completion and inverse (not graphical event delivery)");
        }
        if (args.length > 2) {
            byte[] body = Files.readAllBytes(Path.of(args[2]));
            cvX event = new cvX();
            if (!event.dp(body) || event.bhe() != -1 || event.eII() != 2000 || event.eIK())
                throw new AssertionError("Native world event did not decode retained effect2000");
            iN payload = iN.bf(event.eIJ());
            if (payload.Qs() != 72217 || payload.QA().Mg() <= 0 || payload.Qw() != payload.Qy())
                throw new AssertionError("Native world event lost definition/profession/ownership");
            System.out.println("PASS native12613 retained world carrier decoder");
        }
        System.out.println("PASS native planting arithmetic oracle " + count + " combinations");
    }
}
