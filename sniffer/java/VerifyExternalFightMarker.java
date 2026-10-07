import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;

/** Offline verification of the installed native cuY/13753 reader. */
public final class VerifyExternalFightMarker {
  private VerifyExternalFightMarker() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 1) throw new IllegalArgumentException("expected body hex");
    byte[] body = HexFormat.of().parseHex(Files.readString(Path.of(args[0])).trim());
    cuY marker = new cuY();
    if (!marker.dp(body)) throw new AssertionError("cuY rejected external marker body");
    if (marker.d() != 13753) throw new AssertionError("wrong opcode");
    if (marker.bhe() != 99) throw new AssertionError("wrong fight id");
    if (marker.eHb() != 2) throw new AssertionError("expected native PVE type id 2");
    if (marker.eHc() != 1134L || marker.eHd() != 900001L)
      throw new AssertionError("map/marker identity getters differ");
    if (marker.eHi() != 7001L) throw new AssertionError("model identity getter differs");
    if (marker.eHf().aKg() != 1) throw new AssertionError("phase getter differs");
    if (marker.eHa() != 2 || marker.Mj(0) != 10L || marker.Mj(1) != -20L)
      throw new AssertionError("actor/team table getter differs");
    if (marker.Mk(0) != 0 || marker.Mk(1) != 1)
      throw new AssertionError("actor team getter differs");
    if (marker.eHg().size() != 2 || marker.eHh().size() != 1)
      throw new AssertionError("leader or topology-entry list differs");
    byte[] topology = marker.eHe();
    if (topology.length != 8 || topology[0] != 0x55)
      throw new AssertionError("QI topology tail was not retained");
    System.out.println("native cuY/13753 reader accepted type, map/marker IDs, roster, phase, and topology");
  }
}
