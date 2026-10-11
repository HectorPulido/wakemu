import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

/** Offline native popup visibility check; never modifies the installed client. */
public final class VerifyCorpseMenuVisibility {
    static final class OfflinePlayer extends biB {
        OfflinePlayer() { super(false); }
        @Override public boolean dop() { return false; }
        @Override public void a(PA change) {}
        @Override public bPo drI() { return null; }
        @Override public Qf bax() { return null; }
        @Override public Optional<eTo> dtx() { return Optional.empty(); }
    }

    public static void main(String[] args) throws Exception {
        // This fixture intentionally has no profession sheet: availability may
        // be disabled, but the actual native visibility gate must remain sound.
        Field player = aTx.class.getDeclaredField("hsi");
        player.setAccessible(true);
        player.set(aTx.cWt(), new OfflinePlayer());
        ctE packet = new ctE();
        if (!packet.dp(Files.readAllBytes(Path.of(args[0]))))
            throw new AssertionError("Invalid server appearance");
        eHj appearance = new eHj();
        appearance.ew(packet.eFQ().get(0).aLJ());
        bje target = bje.dsi();
        new eGv(target, appearance.fta()).zm();
        new bjh(target, appearance.fva()).zm();
        if (!target.dsA()) throw new AssertionError("Missing server DEAD19");
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
                + "/%d.jar!/%d.bin");
        Method build = bbo.class.getDeclaredMethod("a", aMb.class, short.class, blj.class);
        build.setAccessible(true);
        int reference = Integer.parseInt(args[1]);
        int[] counts = {0, 0, 0};
        apw.bGL().a(new aMb(), new apB<aMb>() {
            public void load(aMb row) {
                if (reference >= 0 && row.d() != reference) return;
                try {
                    blj breed = blj.iug;
                    build.invoke(null, row, (short) row.d(), breed);
                    for (aMi source : row.csk()) {
                        String expression = source.clT().trim();
                        boolean corpse = expression.equals("IsDead(\"target\")");
                        boolean unrestricted = expression.isEmpty();
                        if (!corpse && !unrestricted && !expression.equals("not IsDead(\"target\")")) continue;
                        boq action = breed.PU(source.d());
                        fyA definition = new fyA(action.clx(), "offline", 0, "offline", new int[0]);
                        definition.setEnabled(true);
                        fyB.gtJ().e(definition);
                        cXc menu = new cXc(action);
                        menu.aK(target);
                        boolean visible = menu.bxQ();
                        if (visible != (corpse || unrestricted))
                            throw new AssertionError("Wrong native popup visibility " + source.d());
                        target.a(eHQ.pSA, (byte) 0);
                        if (menu.bxQ() != (!corpse || unrestricted))
                            throw new AssertionError("Wrong living popup visibility " + source.d());
                        target.a(eHQ.pSA, (byte) 1);
                        if (unrestricted && !target.Ds(source.d()))
                            throw new AssertionError("Server disables native unrestricted action " + source.d());
                        counts[unrestricted ? 2 : (corpse ? 0 : 1)]++;
                        System.out.println("PASS native popup breed=" + row.d() + " action=" + source.d()
                                + " item=" + action.csP() + " corpse=" + corpse
                                + " unrestricted=" + unrestricted + " visible=" + visible
                                + " resourceAvailable=" + target.Ds(source.d()));
                    }
                } catch (Exception error) { throw new RuntimeException(error); }
            }
        });
        if (counts[0] == 0 || counts[1] == 0)
            throw new AssertionError("Both corpse-resource and living-seed actions required");
        System.out.println("Checked corpse actions=" + counts[0] + " living actions=" + counts[1] + " unrestricted actions=" + counts[2]);
        System.out.println("PASS native popup gate: server DEAD19 hides living collection; native corpse seed and hand remain visible/available");
        System.exit(0);
    }
}
