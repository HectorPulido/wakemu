import java.nio.file.*;
import java.util.*;
public final class VerifyCombatJoin {
 public static void main(String[]args)throws Exception{
  cvg add=new cvg();if(!add.dp(Files.readAllBytes(Path.of(args[0])))||add.bhe()!=99||add.OO()!=20||add.bcM()!=0||add.eHD()!=null)throw new AssertionError("cvg13091 mismatch");
  cuY world=new cuY();if(!world.dp(Files.readAllBytes(Path.of(args[1])))||world.bhe()!=99||world.eHb()!=2||world.eHa()!=2||world.Mj(0)!=10||world.Mj(1)!=-200||world.Mk(1)!=1||world.eHg().size()!=2||world.eHh().size()!=1||world.eHf()==null)throw new AssertionError("cuY13753 mismatch");
  VF.dd("jar:file:"+Path.of("client/contents/maps/tplg").toAbsolutePath()+"/%d.jar!/");QI arena=new QI();new fct(arena).eO(java.nio.ByteBuffer.wrap(world.eHe()));
  System.out.println("cvg13091 own actor20; cuY13753 own teams/leaders and native fct topology accepted");
  for(fbZ phase:fbZ.values())System.out.println("phase "+phase.name()+" code "+phase.aKg());
 }
}
