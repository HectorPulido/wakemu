import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

/** Offline native oracle for Python guild snapshots and nonempty format22. */
public final class VerifyGuildSnapshot {
    public static void main(String[] args) throws Exception {
        try {
            byte[] protobuf = Files.readAllBytes(Path.of(args[0]));
            byte[] entity = Files.readAllBytes(Path.of(args[1]));
            jU message = jU.bt(protobuf);
            if (!message.isInitialized()) throw new AssertionError("Missing required protobuf fields");
            fhV guild = fgL.fK(ByteBuffer.wrap(protobuf));
            if (guild.Sn() != 456 || guild.gaM() != 1 || guild.gaN() != 2 || guild.gaO() != 0)
                throw new AssertionError("Guild/rank/member counts or identity mismatch");
            if (guild.jR(999) == null || guild.jT(100) == null || guild.jT(101) == null)
                throw new AssertionError("Member/rank identity missing");
            byte[] carrier = ByteBuffer.allocate(10 + entity.length).putLong(999).putShort((short) entity.length).put(entity).array();
            cyo update = new cyo();
            if (!update.dp(carrier) || !Arrays.equals(entity, update.eLp()))
                throw new AssertionError("15548 carrier decode mismatch");
            if (entity[0] != 22 || eHf.values()[22].fuK().length != 4)
                throw new AssertionError("Unexpected format22 native section list");
            ByteBuffer body = ByteBuffer.wrap(entity);
            body.position(32);
            qH section = new qH();
            if (!section.aG(body) || body.remaining() != 8 || !Arrays.equals(section.VD, protobuf))
                throw new AssertionError("Nonempty format22 local guild parse mismatch");
            if (fgL.fK(ByteBuffer.wrap(section.VD)).jR(999) == null)
                throw new AssertionError("Local guild member missing");
            ByteBuffer encoded = ByteBuffer.allocate(section.DN());
            if (!section.aF(encoded)) throw new AssertionError("Native local guild encode failed");
            if (!Arrays.equals(encoded.array(), Arrays.copyOfRange(entity, 32, entity.length - 8)))
                throw new AssertionError("Native local guild reserialization mismatch");
            if (args.length > 2) {
                byte[] remoteCarrier = Files.readAllBytes(Path.of(args[2]));
                cyo remoteUpdate = new cyo();
                if (!remoteUpdate.dp(remoteCarrier)) throw new AssertionError("Remote carrier rejected");
                byte[] remoteEntity = remoteUpdate.eLp();
                eHe[] sections = eHf.values()[12].fuK();
                if (remoteEntity[0] != 12 || sections.length != 3 || !sections[0].name().equals("NATION_ID") || !sections[1].name().equals("NATION_SYNCHRO") || !sections[2].name().equals("GUILD_REMOTE_INFO"))
                    throw new AssertionError("Unexpected remote update sections");
                ByteBuffer remoteBody = ByteBuffer.wrap(remoteEntity);
                remoteBody.position(32);
                rV remoteGuild = new rV();
                if (!remoteGuild.aG(remoteBody) || remoteBody.hasRemaining() || remoteGuild.Uz != 456 || !remoteGuild.UR.equals("Audit Guild"))
                    throw new AssertionError("Remote guild parse failed");
                System.out.println("PASS native format12 only nation identity/synchronization + guild remote info; bytes=" + remoteCarrier.length);
            }
            System.out.println("PASS native protobuf + fgL member/rank model + cyo15548 + qH nonempty format22; protobuf=" + protobuf.length + " entity=" + entity.length);
        } catch (Throwable failure) {
            failure.printStackTrace();
            System.exit(1);
        }
        System.exit(0);
    }
}
