import java.util.HexFormat;
/** Offline proof of eZR.QH schema and Ts sentinel, with no client connection. */
public class ProbeNativeTimeDatas {
 public static void main(String[] args) {
  Ts t=Ts.biM();
  iB sentinel=iB.Pr().G(false).eB(-1).a(ix.OU().ai(t.OO()).eA(t.biO()).F(t.biN())).aj(-1).H(false).Px();
  iB scheduled=iB.Pr().G(false).eB(-1).a(ix.OU().ai(22).eA(3).F(true)).aj(0).H(false).Px();
  System.out.println(HexFormat.of().formatHex(sentinel.toByteArray()));
  System.out.println(HexFormat.of().formatHex(scheduled.toByteArray()));
 }
}
