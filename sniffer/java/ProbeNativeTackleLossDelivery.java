import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Original tackle factories, cvX decoding, aVo completion and final cuU hydration. */
public final class ProbeNativeTackleLossDelivery {
    static class Effects extends eZV { Effects() { super(null); } }
    static class Step extends aET {
        final Runnable run;
        Step(int id, Runnable run) { super(id, 0, 0); this.run = run; }
        protected long cby() { run.run(); return 0; }
        protected void cbj() {}
    }
    static void set(Object o, Class<?> c, String n, Object value) throws Exception {
        Field field = c.getDeclaredField(n); field.setAccessible(true); field.set(o, value);
    }
    static void check(boolean test, String label) {
        if (!test) throw new AssertionError(label);
        System.out.println("PASS " + label);
    }
    public static void main(String[] args) throws Exception {
        Path dir = Path.of(args[0]);
        int checks = 0;
        for (String kind : new String[] {"player", "npc"}) {
            long id = kind.equals("player") ? 84L : -1125899928606083L;
            var owned = ProbeNativeTackleSnapshots.read(dir.resolve(kind + "-before.bin"), 0, 0, 0, 29);
            int beforeAP = owned.stats.c(ffw.sgD), beforeMP = owned.stats.c(ffw.sgE);
            Effects effects = new Effects();
            PV actor = (PV) Proxy.newProxyInstance(PV.class.getClassLoader(), new Class[] {PV.class}, (p,m,a) -> switch(m.getName()) {
                case "Sn" -> id;
                case "a" -> owned.stats.g((PC)a[0]);
                case "b" -> owned.stats.e((PC)a[0]);
                case "c" -> owned.stats.c((PC)a[0]);
                case "bax" -> effects;
                case "bcz", "bcA" -> 0;
                case "bcB" -> (short) 0;
                case "bav" -> (byte) 0;
                case "bcy" -> aAS.dyA;
                case "toString" -> "TackleFixture" + id;
                case "hashCode" -> System.identityHashCode(p);
                case "equals" -> p == a[0];
                default -> throw new UnsupportedOperationException(m.getName());
            });
            PN context = bcz.dcW();
            String[] costs = Files.readString(dir.resolve(kind + "-cost.txt")).split(",");
            int apLoss = Integer.parseInt(costs[0]), mpLoss = Integer.parseInt(costs[1]);
            fyQ tax = new fyQ(); tax.g((byte)2, apLoss); tax.g((byte)3, mpLoss);
            eZR[] producers = {eZz.b(context, tax, actor), eZA.c(context, tax, actor)};
            aER queue = new aER();
            for (int i = 0; i < 2; i++) {
                cvX wire = new cvX();
                check(wire.dp(Files.readAllBytes(dir.resolve(kind + "-loss-" + i + ".bin"))), kind + " cvX parser"); checks++;
                check(wire.eII() == producers[i].d() && !wire.eIK(), kind + " native tackle family/execute flag"); checks++;
                check(Arrays.equals(wire.eIJ(), producers[i].aqv()), kind + " byte-exact original factory payload " + producers[i].d()); checks++;
                eZR replay = (eZR)eVi.fLJ().pS(wire.eII()).bbn();
                replay.lV(wire.eII()); replay.a(context); replay.ds(wire.eIJ());
                set(replay, Qe.class, "bfs", actor);
                aVo action = new aVo(i + 1, 3, replay.d(), 671, replay, false);
                Method complete = aVo.class.getDeclaredMethod("cYg"); complete.setAccessible(true);
                queue.c(new Step(i + 1, () -> {
                    try { complete.invoke(action); } catch (Exception e) { throw new RuntimeException(e); }
                }));
            }
            queue.c(new Step(3, () -> {
                check(owned.stats.c(ffw.sgD) == beforeAP - apLoss && owned.stats.c(ffw.sgE) == beforeMP - mpLoss,
                        kind + " original aVo completes each tackle surcharge once");
                try { ProbeNativeTackleSnapshots.read(dir.resolve(kind + "-after.bin"), 0, 0, 0, 29, owned); }
                catch (Exception e) { throw new RuntimeException(e); }
            }));
            queue.cbu();
            check(queue.cbt().isEmpty(), kind + " native action queue drained"); checks++;
            check(owned.stats.c(ffw.sgD) == beforeAP - apLoss && owned.stats.c(ffw.sgE) == beforeMP - mpLoss - 1,
                    kind + " final server snapshot preserves ordinary step and no double charge"); checks += 2;
        }
        System.out.println("PASS " + checks + " native tackle delivery checks; no GUI/session claim");
    }
}
