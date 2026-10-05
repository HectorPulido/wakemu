import java.nio.file.*;
/** Original cuU + eHd complete PC sections from real checkpoint snapshot. */
public class ProbeNativeArmorActorRefresh {
 public static void main(String[]args)throws Exception{
  cuU packet=new cuU();packet.dp(Files.readAllBytes(Path.of(args[0])));
  eHd descriptor=new eHk();descriptor.ew(packet.aLJ());
  java.lang.reflect.Method select=eHd.class.getDeclaredMethod("a",eHe.class);select.setAccessible(true);int count=0;
  for(eHe field:eHf.values()[3].fuK()){gp part=(gp)select.invoke(descriptor,field);if(!(part instanceof pl section))continue;count++;
   ffh stats=new ffh();if(!stats.b(section.SS)||stats.e(ffw.shQ).aYS()!=7)throw new AssertionError("PC section armor="+stats.e(ffw.shQ).aYS());
  }
  if(count!=2)throw new AssertionError("sections"+count);
  System.out.println("PASS original cuU12873/eHd complete PC public+private ARMOR7 actor="+packet.KU());
 }
}
