import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** Verify the installed client's actual 22995 decoder without printing tokens. */
public final class VerifyShopAuthentication {
    public static void main(String[] args) throws Exception {
        byte[] payload;
        if (args.length == 1) {
            payload = Files.readAllBytes(Path.of(args[0]));
        } else if (args.length == 0) {
            byte[] token = "local-shop-contract-test".getBytes(StandardCharsets.UTF_8);
            long expiry = System.currentTimeMillis() + 86_400_000L;
            payload = ByteBuffer.allocate(4 + token.length + 8)
                .putInt(token.length).put(token).putLong(expiry).array();
        } else {
            throw new IllegalArgumentException("Expected optional raw 22995 payload path");
        }
        ByteBuffer input = ByteBuffer.wrap(payload);
        int length = input.getInt();
        if (length <= 0 || length > input.remaining() - 8) {
            throw new AssertionError("Invalid authentication token length");
        }
        byte[] token = new byte[length];
        input.get(token);
        long expiry = input.getLong();
        if (input.hasRemaining()) throw new AssertionError("Unexpected trailing bytes");
        long now = System.currentTimeMillis();
        if (expiry <= now || expiry > now + 7L * 86_400_000L) {
            throw new AssertionError("Expected future epoch milliseconds within seven days");
        }
        cEt message = new cEt();
        message.dp(payload);
        if (message.d() != 22995) throw new AssertionError("Unexpected native opcode");
        if (!new String(token, StandardCharsets.UTF_8).equals(message.getKey())) {
            throw new AssertionError("Native decoder changed authentication token");
        }
        if (message.ePu() != expiry) throw new AssertionError("Native expiry mismatch");
        System.out.println("Native 22995 authentication decode OK; token preserved; expiry uses milliseconds.");
    }
}
