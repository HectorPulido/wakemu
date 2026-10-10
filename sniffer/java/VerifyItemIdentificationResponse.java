import java.util.HexFormat;

/** Decode an identification result with the installed native client classes. */
public final class VerifyItemIdentificationResponse {
  public static void main(String[] args) throws Exception {
    if (args.length != 1) throw new IllegalArgumentException("usage: <13766-body-hex>");
    cxh result = new cxh();
    if (!result.dp(HexFormat.of().parseHex(args[0]))) {
      throw new IllegalArgumentException("Native identification parser rejected body");
    }
    fpI sockets = result.eKb();
    foX elements = result.eJZ();
    System.out.println("opcode=" + result.d() + " status=" + result.eKc()
        + " uid=" + result.bTD() + " sockets_present=" + (sockets != null)
        + " socket_count=" + (sockets == null ? 0 : sockets.gjF())
        + " elements_present=" + (elements != null)
        + " elements_pending=" + (elements != null && elements.aKv()));
    if (sockets == null && elements == null) {
      throw new IllegalArgumentException("No state available to native identification UI");
    }
  }
}
