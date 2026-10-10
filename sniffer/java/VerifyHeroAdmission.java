import java.nio.ByteBuffer;
import java.util.Arrays;
import java.nio.file.Files;
import java.nio.file.Path;

/** Verifies cue's native owned-hero admission envelope without graphics. */
public class VerifyHeroAdmission {
    public static void main(String[] args) throws Exception {
        if (args.length > 0) {
            cue actual = new cue();
            actual.dp(Files.readAllBytes(Path.of(args[0])));
            eHk actor = new eHk();
            actor.ew(actual.eGo());
            eQW builds = eQV.ez(actual.eFc());
            eQJ aptitudes = eQx.ey(actual.eFd());
            if (builds.uv().isEmpty() || builds.fHp() == null
                    || !aptitudes.uv().keySet().containsAll(builds.uv().keySet())) {
                throw new AssertionError("missing native build or aptitude sheets");
            }
            if (args.length > 1 && actor.fsS().Vc != Long.parseLong(args[1])) {
                throw new AssertionError("native actor identity");
            }
            System.out.println("PASS actual Python cue12093: native entity " + actor.fsS().Vc
                    + ", build indices " + builds.uv().keySet()
                    + ", aptitude indices " + aptitudes.uv().keySet()
                    + ", account=" + actor.fsR().Vh
                    + ", nation=" + actor.fvS().Wi + ", listNation=" + actor.fvT().Wi
                    + ", guild=" + actor.fvL().Uz);
            return;
        }
        byte[] entity = {1, 2, 3};
        byte[] equipment = {4, 5};
        byte[] spells = {6, 7, 8, 9};
        byte[] body = ByteBuffer.allocate(12 + entity.length + equipment.length + spells.length)
                .putInt(entity.length).put(entity)
                .putInt(equipment.length).put(equipment)
                .putInt(spells.length).put(spells).array();
        cue packet = new cue();
        // The native decoder returns false even after populating all three fields.
        packet.dp(body);
        if (packet.d() != 12093 || !Arrays.equals(entity, packet.eGo())
                || !Arrays.equals(equipment, packet.eFc())
                || !Arrays.equals(spells, packet.eFd())) {
            throw new AssertionError("owned hero admission envelope");
        }
        System.out.println("PASS native cue12093 entity/equipment/spell envelope; consumer requires graphics");
    }
}
