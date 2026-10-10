import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;

/** Exercises the installed client's complete configuration decoder offline. */
public class VerifyHeroesConfiguration {
    public static void main(String[] args) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        out.writeInt(4);
        int[] ids = {431, 602, 603, 622};
        String[] values = {"true", "true", "true", "2"};
        for (int i = 0; i < ids.length; i++) {
            byte[] value = values[i].getBytes(StandardCharsets.UTF_8);
            out.writeShort(ids[i]);
            out.writeInt(value.length);
            out.write(value);
        }
        byte[] payload = bytes.toByteArray();
        cEo message = new cEo();
        if (!message.dp(ByteBuffer.allocate(4 + payload.length)
                .putInt(payload.length).put(payload).array()) || message.d() != 23053) {
            throw new AssertionError("configuration envelope");
        }
        eEI configuration = new eEI();
        configuration.dT(message.aLJ());
        if (!configuration.l(eEL.pbt) || !configuration.l(eEL.pce)
                || !configuration.l(eEL.pcf) || configuration.j(eEL.pcq) != 2) {
            throw new AssertionError("hero configuration values");
        }
        configuration.dT(ByteBuffer.allocate(4).putInt(0).array());
        if (configuration.i(eEL.pce) || configuration.l(eEL.pce)) {
            throw new AssertionError("snapshot must clear previous overrides");
        }
        System.out.println("PASS native 23053 envelope, hero options and snapshot replacement");
    }
}
