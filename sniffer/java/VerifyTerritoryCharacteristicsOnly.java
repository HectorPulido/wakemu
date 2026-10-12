import java.nio.file.Files;
import java.nio.file.Path;
import java.util.EnumMap;
import java.util.Map;

/** Actual native section decoder: a regional stat refresh cannot carry position. */
public final class VerifyTerritoryCharacteristicsOnly {
    static Map<eHe,String> snapshot(eHk entity) {
        Map<eHe,String> values = new EnumMap<>(eHe.class);
        for (eHe section : eHf.values()[3].fuK()) {
            gp reader = entity.a(section);
            if (reader != null) values.put(section, reader.toString());
        }
        return values;
    }
    public static void main(String[] args) throws Exception {
        eHf format = eHf.values()[39];
        if (format.fuK().length != 1 || format.fuK()[0] != eHe.pLO || eHe.pLO.ordinal() != 53)
            throw new AssertionError("Native format 39 must select only public characteristics 53");
        eHk entity = new eHk();
        entity.ew(Files.readAllBytes(Path.of(args[0])));
        Map<eHe,String> before = snapshot(entity);
        csZ packet = new csZ();
        if (!packet.dp(Files.readAllBytes(Path.of(args[1]))) || packet.d() != 13046)
            throw new AssertionError("Native actor refresh envelope rejected");
        if (Byte.toUnsignedInt(packet.eFf()[0]) != 39)
            throw new AssertionError("Expected public-characteristics-only refresh");
        entity.ew(packet.eFf());
        Map<eHe,String> after = snapshot(entity);
        int preserved = 0;
        for (eHe section : before.keySet()) {
            if (section == eHe.pLO) continue;
            if (!before.get(section).equals(after.get(section)))
                throw new AssertionError("Stats-only refresh changed native section " + section);
            preserved++;
        }
        if (before.get(eHe.pLO).equals(after.get(eHe.pLO)))
            throw new AssertionError("Public characteristics did not update");
        entity.ew(Files.readAllBytes(Path.of(args[2])));
        Map<eHe,String> negative = snapshot(entity);
        int changed = 0;
        for (eHe section : before.keySet()) {
            if (section != eHe.pLO && !after.get(section).equals(negative.get(section))) changed++;
        }
        if (changed == 0) throw new AssertionError("Old full refresh negative control did not change position/state");
        System.out.println("PASS native csZ/eHk.ew format39 section53 only; preserved=" + preserved
            + " non-stat sections; old format3 changed=" + changed + " non-stat sections");
    }
}
