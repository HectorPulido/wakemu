import java.nio.file.*;
import java.nio.*;
import java.util.*;

/** Independent installed-client decoder oracle for tactical marker packets. */
public class VerifyCombatTacticalPackets {
    public static void main(String[] args) throws Exception {
        int opcode = Integer.parseInt(args[0]);
        byte[] body = Files.readAllBytes(Path.of(args[1]));
        if (opcode == 13788) {
            cuT packet = new cuT();
            if (!packet.dp(body)) throw new IllegalArgumentException("Native cell report decoder rejected body");
            System.out.printf("opcode=%d fight=%d x=%d y=%d z=%d sender=%d%n", packet.d(), packet.bhe(),
                packet.eGX().getX(), packet.eGX().getY(), packet.eGX().bdn(), packet.eGY());
        } else if (opcode == 12226) {
            cvj packet = new cvj();
            if (!packet.dp(body)) throw new IllegalArgumentException("Native marker decoder rejected body");
            if (packet.dNq() == null) throw new IllegalArgumentException("Native marker icon did not resolve");
            System.out.printf("opcode=%d fight=%d x=%d y=%d z=%d sender=%d icon=%d added=%s%n", packet.d(), packet.bhe(),
                packet.eHF().getX(), packet.eHF().getY(), packet.eHF().bdn(), packet.eGY(),
                packet.dNq().aKg(), packet.eHG());
        } else if (opcode == 12543 || opcode == 12519 || opcode == 12597) {
            int expected = opcode == 12543 ? 10 : 11;
            if (body.length != expected) throw new IllegalArgumentException("Wrong native request length");
            ByteBuffer fields = ByteBuffer.wrap(body);
            aBn position = new aBn(fields.getInt(), fields.getInt(), fields.getShort());
            byte[] serialized;
            if (opcode == 12543) {
                coNN packet = new coNN(); packet.aa(position); serialized = packet.aWH();
            } else {
                byte icon = fields.get();
                fdk type = Arrays.stream(fdk.values()).filter(v -> v.aKg() == icon).findFirst().orElseThrow();
                if (opcode == 12519) {
                    coV packet = new coV(); packet.aa(position); packet.c(type); serialized = packet.aWH();
                } else {
                    coW packet = new coW(); packet.aa(position); packet.c(type); serialized = packet.aWH();
                }
            }
            byte[] tail = Arrays.copyOfRange(serialized, serialized.length - expected, serialized.length);
            if (!Arrays.equals(tail, body)) throw new IllegalArgumentException("Native request serializer differs");
            System.out.printf("opcode=%d body_matches_native=true bytes=%d%n", opcode, expected);
        } else {
            throw new IllegalArgumentException("Unsupported tactical opcode");
        }
    }
}
