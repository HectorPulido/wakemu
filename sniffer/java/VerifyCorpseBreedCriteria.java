import java.lang.reflect.Method;
import java.nio.file.Path;

/** Exercise actual binary breed action loading, not reconstructed criteria. */
public final class VerifyCorpseBreedCriteria {
    public static void main(String[] args) throws Exception {
        int reference = args.length == 0 ? 1 : Integer.parseInt(args[0]);
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
                + "/%d.jar!/%d.bin");
        Method build = bbo.class.getDeclaredMethod("a", aMb.class, short.class, blj.class);
        build.setAccessible(true);
        blj breed = blj.iug;
        int[] checked = {0};
        apw.bGL().a(new aMb(), new apB<aMb>() {
            public void load(aMb row) {
                if (row.d() != reference) return;
                try {
                    // apw reuses/reset its row: inspect inside the real load callback.
                    build.invoke(null, row, (short) reference, breed);
                    for (aMi source : row.csk()) {
                        String expression = source.clT().trim();
                        boolean corpse = expression.equals("IsDead(\"target\")");
                        if (!corpse && !expression.equals("not IsDead(\"target\")")) continue;
                        boq action = breed.PU(source.d());
                        amb criterion = action == null ? null : action.bdt();
                        if (criterion == null) throw new AssertionError("Dropped criterion " + source.d());
                        bje target = bje.dsi();
                        boolean alive = criterion.b(null, target, null, null);
                        target.a(eHQ.pSA, (byte) 1);
                        boolean dead = criterion.b(null, target, null, null);
                        if (alive == corpse || dead != corpse)
                            throw new AssertionError("Wrong actual breed life criterion " + source.d());
                        checked[0]++;
                        System.out.println("PASS native breed=" + reference + " action=" + source.d()
                                + " item=" + action.csP() + " alive=" + alive + " dead=" + dead);
                    }
                } catch (Exception error) {
                    throw new RuntimeException(error);
                }
            }
        });
        if (checked[0] == 0) throw new AssertionError("No explicit life-state actions checked");
    }
}
