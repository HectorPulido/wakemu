import java.lang.reflect.Field;
import java.util.HashMap;
import java.util.Map;

/** Original-client arithmetic oracle. Private JVM only; no catalog or config writes. */
public final class ProbeEnvironmentalRewardArithmetic {
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        Field configField = eEI.class.getDeclaredField("oZz");
        configField.setAccessible(true);
        Map<Object, Object> config = (Map<Object, Object>) configField.get(eEI.oZx);
        Map<Object, Object> saved = new HashMap<>(config);
        int checks = 0;
        try {
            // Mutate only this private JVM's map, never a setter that persists config.
            for (String ratioText : new String[]{"0.7692", "1", "0.33333334"}) {
                for (String bonusText : new String[]{"0", "50", "37"}) {
                    config.put(eEL.pdn, Float.valueOf(ratioText));
                    config.put(eEL.pdo, Integer.valueOf(bonusText));
                    float ratio = Float.parseFloat(ratioText);
                    float boosted = ratio * (1.0f + Integer.parseInt(bonusText) / 100.0f);
                    if (Float.floatToIntBits(eEn.oUH.foX()) != Float.floatToIntBits(ratio)
                            || Float.floatToIntBits(eEn.Pv(eEn.oUH.foV()).foX())
                               != Float.floatToIntBits(boosted))
                        throw new AssertionError("Original subscription ratio differs");
                    for (double base : new double[]{0, 1, 2, 17, 118105143, 2147483647}) {
                        long normal = Math.round(base * (double) ratio);
                        long extra = Math.round(base * (double) (boosted - ratio));
                        if (fCn.ae(base) != normal || fCn.af(base) != extra)
                            throw new AssertionError("Original float32/double XP display differs");
                        checks++;
                    }
                }
            }
        } finally {
            config.clear();
            config.putAll(saved);
        }
        for (long seconds : new long[]{1, 120, 600, 900, 1800, 3600}) {
            TS duration = TS.fm(seconds);
            if (duration.bjT() != seconds || duration.bjC() != seconds * 1000L
                    || TS.fn(seconds * 1000L).bjT() != seconds)
                throw new AssertionError("Original duration seconds conversion differs");
        }
        System.out.println("PASS original XP display: " + checks
                + " vectors; original duration: 6 seconds/milliseconds vectors");
    }
}
