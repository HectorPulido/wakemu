import java.nio.file.*;
/** Offline installed native codec oracle for server-generated captured NPC. */
public class VerifyCapturedNpcInitialScene {
    static void check(boolean condition) { if (!condition) throw new AssertionError(); }
    public static void main(String[] args) throws Exception {
        ctE packet = new ctE();
        check(packet.dp(Files.readAllBytes(Path.of(args[0]))));
        check(packet.eFQ().size() == 1);
        ctF actor = packet.eFQ().get(0);
        check(actor.aGJ() == 1 && actor.Sn() == -1706442035962340L);
        eHj entity = new eHj(); entity.ew(actor.aLJ());
        check(entity.fsS().Vc == actor.Sn());
        rE position = entity.fsV();
        check(position.XC == -12 && position.XD == 0 && position.XE == 2 && position.Vp == 1387);
        cuz dialogue = new cuz();
        check(dialogue.dp(Files.readAllBytes(Path.of(args[1]))));
        check(dialogue.dCX() == 5764 && dialogue.czY() == actor.Sn());
        check(dialogue.eGI().aKg() == 2);
        System.out.println("PASS native ctE/eHj original identity/map/XYZ and cuz initial dialogue5764 speaker2");
    }
}
