import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;

/** Native selected cosmetic actor component, preserving non-costume fields. */
public final class VerifyCostumeActorComponent {
    public static void main(String[] args) throws Exception {
        ByteBuffer body = ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));
        pq component = new pq();
        if (!component.aG(body) || body.hasRemaining() || component.Tb.abs == null)
            throw new AssertionError("Invalid selected cosmetics actor component");
        tG selected = component.Tb.abs;
        if (selected.abt != Integer.parseInt(args[1]))
            throw new AssertionError("Unexpected native costume reference");
        if (args.length > 2 && selected.abv != Integer.parseInt(args[2]))
            throw new AssertionError("Unexpected native sprint reference");
        if (args.length > 3 && selected.abw != Integer.parseInt(args[3]))
            throw new AssertionError("Unexpected native aura reference");
        if (args.length > 4 && Short.toUnsignedInt(selected.abx) != Integer.parseInt(args[4]))
            throw new AssertionError("Unexpected native title ID");
        if (fn.px.getNumber() != 3)
            throw new AssertionError("Unexpected native PLAYER_COSTUME category");
        ByteBuffer roundtrip = ByteBuffer.allocate(component.DN());
        if (!component.aF(roundtrip) || roundtrip.hasRemaining())
            throw new AssertionError("Native component round trip failed");
        System.out.println("PASS native pq/tF/tG costume=" + selected.abt
            + " hat=" + selected.abu + " sprint=" + selected.abv
            + " aura=" + selected.abw + " title=" + selected.abx);
    }
}
