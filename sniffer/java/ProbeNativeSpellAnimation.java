/** Decode captured cast payload with the installed client's original handlers.
 * Usage: ProbeNativeSpellAnimation opcode payloadHex actor reference level.
 * No game runtime or network connection is created.
 */
public final class ProbeNativeSpellAnimation {
    public static void main(String[] args) {
        int opcode = Integer.parseInt(args[0]);
        byte[] payload = java.util.HexFormat.of().parseHex(args[1]);
        long expectedActor = Long.parseLong(args[2]);
        int expectedReference = Integer.parseInt(args[3]);
        int expectedLevel = Integer.parseInt(args[4]);
        long actor;
        yy spell;
        int x, y;
        short z;
        boolean critical, failed;
        if (opcode == 12588) {
            cwa packet = new cwa();
            if (!packet.dp(payload)) throw new AssertionError("cwa rejected payload");
            actor = packet.Qw(); spell = packet.eIA();
            x = packet.eIM(); y = packet.eIN(); z = packet.eIO();
            critical = packet.cXj(); failed = packet.cXk();
        } else if (opcode == 12678) {
            cwb packet = new cwb();
            if (!packet.dp(payload)) throw new AssertionError("cwb rejected payload");
            actor = packet.Qw(); spell = packet.eIR();
            if (packet.eIQ() != expectedReference) throw new AssertionError("chat reference");
            x = packet.getX(); y = packet.getY(); z = packet.bdn();
            critical = packet.cXj(); failed = packet.cXk();
        } else throw new IllegalArgumentException("Unsupported opcode");
        if (actor != expectedActor || spell.amm != expectedReference || spell.Yf != expectedLevel)
            throw new AssertionError("Native decoded spell identity mismatch");
        System.out.printf("PASS opcode=%d actor=%d reference=%d level=%d uid=%d target=%d,%d,%d critical=%s failed=%s%n",
            opcode, actor, spell.amm, spell.Yf, spell.aaq, x, y, z, critical, failed);
    }
}
