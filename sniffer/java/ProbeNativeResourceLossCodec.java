import java.nio.file.*;
/** Original cvY/eVZ decoder validates owned MP/AP loss identities and rCB. */
public class ProbeNativeResourceLossCodec {
 public static void main(String[] args)throws Exception {
  int family=Integer.parseInt(args[1]);int value=Integer.parseInt(args[2]);
  cvY packet=new cvY();
  if(!packet.dp(Files.readAllBytes(Path.of(args[0])))||packet.eII()!=family)
   throw new AssertionError("Native cvY loss family");
  eVZ runner=new eVZ(family==48?ffw.sgE:ffw.sgD);runner.lV(family);
  iN payload=runner.ds(packet.eIJ());
  if(payload==null||runner.getValue()!=value||runner.Mt()!=0||
     runner.fNI()!=(family==48?ffw.sgE:ffw.sgD)||payload.Qw()!=7||payload.Qy()!=-7)
   throw new AssertionError("Native loss value/stat/origin/actors");
  System.out.println("PASS native cvY/eVZ "+family+" actual="+value+" Mt=0");
 }
}
