import java.nio.file.*;import java.lang.reflect.*;import java.util.*;
/** Decode actual Python cvY13497 then execute original eWx client c and removal. */
public class ProbeNativeArmorClient {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[]args)throws Exception{
  cvY packet=new cvY();if(!packet.dp(Files.readAllBytes(Path.of(args[0]))))throw new AssertionError("packet");
  eWx effect=(eWx)eVi.fLJ().pS(packet.eII()); effect=(eWx)effect.b((PN)null);
  iN proto=effect.ds(packet.eIJ());if(proto==null)throw new AssertionError("decode");
  Map<PC,fff> stats=new HashMap<>();ProbeCombatArithmetic.put(stats,ffw.shQ,0);
  PV actor=ProbeCombatArithmetic.actor(stats,0);
  set(effect,Qe.class,"bfr",actor);set(effect,Qe.class,"bfs",actor);
  Method c=eWW.class.getDeclaredMethod("c",Qe.class,boolean.class);c.setAccessible(true);c.invoke(effect,null,false);
  int applied=stats.get(ffw.shQ).aYS();if(applied!=7)throw new AssertionError("client armor="+applied);
  Method remove=eWQ.class.getDeclaredMethod("fNM");remove.setAccessible(true);remove.invoke(effect);
  if(stats.get(ffw.shQ).aYS()!=0)throw new AssertionError("removal");
  System.out.println("cvY/eWx original applied7/removal0 UID="+proto.LV()+" target="+proto.Qy()+" additional="+HexFormat.of().formatHex(proto.QA().toByteArray()));
 }
}
