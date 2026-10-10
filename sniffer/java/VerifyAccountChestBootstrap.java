import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;

/** Offline verification with the installed client's cxt/lY/lj decoders. */
public final class VerifyAccountChestBootstrap {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("Expected file containing a 318 body as hex");
        }
        byte[] body = HexFormat.of().parseHex(Files.readString(Path.of(args[0])).trim());
        cxt message = new cxt();
        if (!message.dp(body) || !message.eKv() || message.eKu().size() != 1) {
            throw new AssertionError("Invalid complete chest bootstrap");
        }
        lY compartment = message.eKu().get(0);
        if (!compartment.isInitialized() || compartment.xl() <= 0 || compartment.ajw() != 100) {
            throw new AssertionError("Invalid owned compartment/capacity");
        }
        for (lj item : compartment.ajA().ot()) {
            if (!item.isInitialized() || item.Lz() < 0 || item.Lz() >= compartment.ajw()) {
                throw new AssertionError("Invalid stored native item/position");
            }
        }
        System.out.println("PASS native cxt/lY/lj bootstrap: capacity=" + compartment.ajw()
            + ", items=" + compartment.ajA().ov() + ", complete=true");
    }
}
