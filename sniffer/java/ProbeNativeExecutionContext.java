import java.util.HexFormat;
/** Real eVt constructor and scalar-mutator ir serialization oracle. */
public class ProbeNativeExecutionContext {
    public static void main(String[] args) {
        eVt original = new eVt();
        System.out.println("fresh " + HexFormat.of().formatHex(original.fLV().toByteArray()));
        original.SP(3);
        original.mb(false);
        original.mc(true);
        original.fLQ();
        original.a(-17, eVu.ryw);
        System.out.println("changed " + HexFormat.of().formatHex(original.fLV().toByteArray()));
    }
}
