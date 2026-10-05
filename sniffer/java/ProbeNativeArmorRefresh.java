import java.nio.*;import java.nio.file.*;import java.util.*;
/** Live checkpoint tA -> ffh updates existing armor object and notifies HUD PD. */
public class ProbeNativeArmorRefresh {
 public static void main(String[]args)throws Exception{
  ffh live=new ffh();fff original=live.e(ffw.shQ);original.on(0);
  List<Integer>notifications=new ArrayList<>();live.a((PD)(stat)->{if(stat.aZh()==ffw.shQ)notifications.add(stat.aYS());});
  ByteBuffer buffer=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));tA payload=new tA();
  if(!payload.aG(buffer)||buffer.hasRemaining()||!live.b(payload))throw new AssertionError("decode");
  if(live.e(ffw.shQ)!=original||original.aYS()!=7||!notifications.contains(7))throw new AssertionError("armor refresh "+original.aYS()+" notifications"+notifications);
  System.out.println("PASS live checkpoint native tA/ffh armor7 same object; HUD PD notifications="+notifications);
 }
}
