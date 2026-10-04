import java.nio.*;import java.nio.file.*;import java.util.*;
/** Read-only own-fixture native ACK and reopen registry codec validation. */
public class ProbeRingBuildCodec {
 public static void main(String[]args)throws Exception {
  long owner=Long.parseLong(args[2]),uid=Long.parseLong(args[3]);
  byte[] packet=Files.readAllBytes(Path.of(args[0]));ByteBuffer b=ByteBuffer.wrap(packet);
  int n=b.getInt();if(n!=b.remaining())throw new AssertionError("registry length");
  byte[] proto=new byte[n];b.get(proto);List<fpl> decoded=fpi.eO(proto);
  if(decoded.size()!=1||decoded.get(0).KU()!=owner)throw new AssertionError("owner");
  fpl registry=decoded.get(0);fpj own=registry.uv().get(0);
  fnO ring=fnO.gf((byte)7);if(!Objects.equals(own.t(ring),uid))throw new AssertionError("registry ring UID");
  fpo.sPn.a(owner,owner,registry);
  fpj reopened=fpo.sPn.aN(owner,owner).uv().get(0);
  if(!Objects.equals(reopened.t(ring),uid))throw new AssertionError("reopen ring UID");
  ctU ack=new ctU();ack.dp(Files.readAllBytes(Path.of(args[1])));if(!ack.eGb()||ack.eGi().aIm())throw new AssertionError("ACK status");
  if(ack.KU()!=owner||ack.eGh()!=0||!Objects.equals(ack.dqw().t(ring),uid))throw new AssertionError("ACK ring UID");
  if(ack.dqw().geO().size()!=1||reopened.geO().size()!=1)throw new AssertionError("duplicate ring");
  System.out.println("PASS native ring ACK+fpo registry reopen: one real UID in slot7, owner/build0 coherent");
 }
}
