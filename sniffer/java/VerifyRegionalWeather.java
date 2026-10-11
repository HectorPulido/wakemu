import java.lang.reflect.Field;
import java.nio.ByteBuffer;
import java.util.HexFormat;
import java.util.List;

/** Decode real server packets and run the installed native weather models. */
public final class VerifyRegionalWeather {
    private static float privateFloat(bRW model, String name) throws Exception {
        Field field = bRW.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.getFloat(model);
    }

    private static void equal(float actual, float expected, String name) {
        if (Math.abs(actual - expected) > 0.00001f) {
            throw new AssertionError(name + ": " + actual + " != " + expected);
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("current13948 forecast13895 next13948 hex");
        ctm current = new ctm();
        if (!current.dp(HexFormat.of().parseHex(args[0]))) throw new AssertionError("current decode");
        ctm next = new ctm();
        if (!next.dp(HexFormat.of().parseHex(args[2]))) throw new AssertionError("next decode");

        // Exact argument mapping from installed chl.b's 13948 branch.
        bRW now = new bRW();
        now.a(current.eFv(), current.eFw(), current.eFx(), current.eFy(), current.eFz(), current.blE());
        now.a(current.eFu() + current.eFx(), 0, 0, 0, null,
              current.blE(), current.blv(), 0);
        equal(now.blu(), (current.eFv() + current.eFw()) / 2 + current.eFx(), "current temperature");
        equal(now.blD(), current.blv(), "current wind ratio");
        equal(privateFloat(now, "lan"), current.eFv() + current.eFx(), "environment minimum");
        equal(privateFloat(now, "lao"), current.eFw() + current.eFx(), "environment maximum");

        byte[] packet = HexFormat.of().parseHex(args[1]);
        ByteBuffer envelope = ByteBuffer.wrap(packet);
        int length = Short.toUnsignedInt(envelope.getShort());
        if (length != envelope.remaining()) throw new AssertionError("forecast envelope");
        bRV decoded = new bRV();
        decoded.fe(envelope.slice());
        bRY panel = bRY.eoC();
        panel.b(now);
        panel.b(decoded);
        equal(panel.eoH().eoB().blu(), now.blu(), "native current panel");
        equal((Float) panel.eoH().eH("windStrength"), now.blD(), "native current wind field");
        List<?> days = (List<?>) panel.eH("weatherOfDays");
        if (days.isEmpty()) throw new AssertionError("forecast days");
        bRX day = (bRX) days.get(0);
        bRW future = day.eoB();
        equal(future.eot(), next.eFv(), "future minimum matches next actual day");
        equal(future.eou(), next.eFw(), "future maximum matches next actual day");
        equal(future.blD(), next.blv(), "future wind matches next actual day");
        if (future.blE() != next.blE()) throw new AssertionError("future weather enum");
        if (future.eov() > future.eot() || future.eow() < future.eou()) {
            throw new AssertionError("native season bounds flatten forecast temperatures");
        }
        String low = (String) day.eH("minTemperatureWithMods");
        String high = (String) day.eH("maxTemperatureWithMods");
        if (!low.startsWith(String.format("%.0f", future.eot()))
                || !high.startsWith(String.format("%.0f", future.eou()))) {
            throw new AssertionError("native displayed forecast bounds: " + low + " / " + high);
        }
        System.out.println("PASS: installed ctm/chl argument mapping, bRW current/environment values, bRY/bRX forecast and panel fields");
    }
}
