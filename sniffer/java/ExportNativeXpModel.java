import java.nio.file.Files;
import java.nio.file.Path;

/** Execute original XP methods offline; no game session or client modification. */
public final class ExportNativeXpModel {
    public static void main(String[] args) throws Exception {
        StringBuilder out = new StringBuilder("{\"source\":\"Original Wakfu MU.L, MT.nS and MP.aXu\",\"levels\":[");
        for (int level = 1; level <= 245; level++) {
            if (level > 1) out.append(',');
            out.append("{\"level\":").append(level)
               .append(",\"monster_base_xp\":").append(MU.L((short) level))
               .append(",\"intended_fights\":").append(MT.nS(level))
               .append(",\"threshold\":").append(MP.aXu.nT(level)).append('}');
        }
        out.append("],\"high_npc_levels\":[");
        int[] high = {246, 500, 1000, 1050, 1100, 32767};
        for (int index = 0; index < high.length; index++) {
            if (index > 0) out.append(',');
            out.append("{\"level\":").append(high[index])
               .append(",\"monster_base_xp\":").append(MU.L((short) high[index])).append('}');
        }
        out.append("]}");
        Files.writeString(Path.of(args[0]), out.toString());
        System.out.println("PASS original Wakfu XP model export through245 and native high-level saturation");
    }
}
