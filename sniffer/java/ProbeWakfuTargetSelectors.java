import java.lang.reflect.Proxy;
/** Offline proof for fcE target relation flags and area application. */
public class ProbeWakfuTargetSelectors {
    static amO actor(byte team, long identity) {
        return actor(team, identity, true, (byte) 0);
    }
    static amO actor(byte team, long identity, boolean eligible, byte nativeTeam) {
        return (amO) Proxy.newProxyInstance(amO.class.getClassLoader(),
            new Class<?>[]{amO.class, QK.class}, (proxy, method, args) -> switch(method.getName()) {
                case "bcM" -> team;
                case "Sn" -> identity;
                case "bEe" -> eligible;
                case "bcN" -> nativeTeam;
                case "bcy" -> aAS.dyA;
                case "bcz", "bcA" -> 0;
                case "bcB" -> (short) 0;
                case "bcK" -> (byte) 0;
                case "toString" -> "actor" + identity;
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }
    public static void main(String[] args) throws Exception {
        amO self = actor((byte) 0, 1), ally = actor((byte) 0, 2), enemy = actor((byte) 1, 3);
        long[] masks = {0, 1, 2, 3, 4, 5, 8, 9, 256, 257, 261};
        String[][] expected = {
            {"VALID", "VALID", "VALID"},
            {"VALID_IF_IN_AOE", "VALID_IF_IN_AOE", "VALID_IF_IN_AOE"},
            {"VALID", "INVALID", "INVALID"},
            {"VALID_IF_IN_AOE", "INVALID", "INVALID"},
            {"VALID", "VALID", "INVALID"},
            {"VALID_IF_IN_AOE", "VALID_IF_IN_AOE", "INVALID"},
            {"INVALID", "INVALID", "VALID"},
            {"INVALID", "INVALID", "VALID_IF_IN_AOE"},
            {"INVALID", "VALID", "VALID"},
            {"INVALID", "VALID_IF_IN_AOE", "VALID_IF_IN_AOE"},
            {"INVALID", "VALID_IF_IN_AOE", "INVALID"}
        };
        var field = fcE.class.getDeclaredField("rXt"); field.setAccessible(true);
        for(int i = 0; i < masks.length; i++) {
            fcE selector = fcE.j(new long[]{masks[i]});
            if(field.getLong(selector) != masks[i]) throw new AssertionError("Unexpected selector mask");
            amO[] targets = {self, ally, enemy};
            System.out.print("mask=" + masks[i]);
            for(int j=0; j<targets.length; j++) {
                String result = selector.a(targets[j], self).toString();
                if(!result.equals(expected[i][j])) throw new AssertionError(masks[i] + ":" + result);
                System.out.print(" " + result);
            }
            System.out.println();
        }
        fcE activeTeam = fcE.j(new long[]{1L | (1L << 50)});
        if (!activeTeam.a(enemy, self).toString().equals("VALID_IF_IN_AOE")) throw new AssertionError("active team");
        if (!activeTeam.a(actor((byte) 1, 4, true, (byte) -1), self).toString().equals("INVALID")) throw new AssertionError("inactive team");
        if (!fcE.j(new long[]{1L}).a(actor((byte) 1, 5, false, (byte) 0), self).toString().equals("INVALID")) throw new AssertionError("bEe false");
        if (!fcE.j(new long[]{0L}).a(actor((byte) 1, 5, false, (byte) 0), self).toString().equals("VALID")) throw new AssertionError("mask0 bypass");
        if (!fcE.j(new long[]{129L}).a(self, self).toString().equals("INVALID")) throw new AssertionError("same team excludes self");
        if (!fcE.j(new long[]{129L}).a(ally, self).toString().equals("VALID_IF_IN_AOE")) throw new AssertionError("same team ally");
        if (!fcE.j(new long[]{1L | (1L << 47)}).a(enemy, self).toString().equals("INVALID")) throw new AssertionError("character type");
        System.out.println("fcE relation, area, active-team, eligibility and character flags verified");
    }
}
