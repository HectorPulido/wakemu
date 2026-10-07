import java.util.HexFormat;

/** Reads one Python-produced native response body with installed client codecs. */
public final class VerifySocketEnchantmentResponse {
  public static void main(String[] args) throws Exception {
    if (args.length != 2) throw new IllegalArgumentException("usage: <opcode> <hex-body>");
    int opcode = Integer.parseInt(args[0]);
    byte[] body = HexFormat.of().parseHex(args[1]);
    cxA response = switch (opcode) {
      case 13703 -> new cxy();
      case 12920 -> new cxz();
      case 13983 -> new cxv();
      case 13793 -> new cxw();
      case 13283 -> new cxB();
      default -> throw new IllegalArgumentException("unsupported response opcode " + opcode);
    };
    if (!response.dp(body)) throw new IllegalArgumentException("client parser rejected response");
    if (response.eKx().aIm()) {
      if (body.length != 1) throw new IllegalArgumentException("failure response carried trailing bytes");
      System.out.println("status=" + response.eKx().name());
      return;
    }
    byte[] shard = fpK.e(response.eKB());
    System.out.print("status=" + response.eKx().name()
        + " character_id=" + response.eKA()
        + " uid=" + response.eGf()
        + " proto_shard=" + HexFormat.of().formatHex(shard));
    if (response instanceof cxy withAction) System.out.print(" action=" + withAction.eKy().name());
    if (response instanceof cxz withAction) System.out.print(" action=" + withAction.eKz().name());
    System.out.println();
  }
}
