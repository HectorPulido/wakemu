import java.nio.file.Files;
import java.nio.file.Path;
/** Decode a server-produced ordinary eWt447 application in the real client. */
public class ProbeNativeFightPropertyCodec {
 public static void main(String[] args) throws Exception {
  cvY packet=new cvY();
  if(!packet.dp(Files.readAllBytes(Path.of(args[0])))||packet.eII()!=447)
   throw new AssertionError("cvY family447");
  eWt runner=new eWt();runner.lV(447);
  iN data=runner.ds(packet.eIJ());
  if(data==null||runner.LV()!=903||runner.getValue()!=11
      ||data.Qs()!=348444||data.Qw()!=7||data.Qy()!=-7||data.Qz())
   throw new AssertionError("ordinary eWt identity/value or unexpected AdditionalDatas");
  if(ffe.Ua(11)==null||ffe.Ua(11)==ffe.sdC||ffe.Ua(11)==ffe.sdO)
   throw new AssertionError("ordinary property authority");
  System.out.println("PASS native cvY447 -> eWt UID903 reference348444 property11 caster7 target-7, no position data");
 }
}
