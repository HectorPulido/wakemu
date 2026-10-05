import java.nio.file.*;import java.lang.reflect.*;
/** Detached original bjo refresh; never connects or touches a running client. */
public class ProbeNativeStateSnapshotRefresh {
 static void set(Object obj,Class<?> cls,String name,Object value)throws Exception{Field f=cls.getDeclaredField(name);f.setAccessible(true);f.set(obj,value);}
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");fyZ.guX().a(new bbV());
  bjo actor=new bjo();set(actor,eGj.class,"aHm",34L);
  byte[] snapshot=Files.readAllBytes(Path.of(args[2]));actor.a(snapshot,false);
  System.out.println("snapshot initialized Qf="+actor.bax()+" stat67="+actor.e(ffw.shA).aYS());
  eZk carrier=new eZk();carrier.lV(310);carrier.a(bcz.dcW());carrier.ds(Files.readAllBytes(Path.of(args[0])));set(carrier,Qe.class,"bfr",actor);set(carrier,Qe.class,"bfs",actor);
  ProbeNativeStateManager.Complete c=new ProbeNativeStateManager.Complete(carrier,actor,actor);c.cYb();c.fe(34);c.iD(34);c.cYc();c.cbj();
  eXE child=new eXE();child.lV(400);child.a(bcz.dcW());child.ds(Files.readAllBytes(Path.of(args[1])));set(child,Qe.class,"bfr",actor);set(child,Qe.class,"bfs",actor);eVn pk=bcA.dcX().AH(150327);set(child,Qe.class,"bfp",pk);
  ProbeNativeStateChildDelivery.Complete a=new ProbeNativeStateChildDelivery.Complete(child,actor,actor);a.cYb();a.fe(34);a.iD(34);aER queue=new aER();queue.c(a);queue.cbu();
  int before=actor.drJ().fSs().size();bPE visible=new bPG().c(child,-1);
  System.out.println("before refresh carriers="+before+" display="+(visible==null?0:visible.elp())+" stat67="+actor.e(ffw.shA).aYS());
  actor.a(snapshot,false);visible=new bPG().c(child,-1);
  int after=actor.drJ().fSs().size();System.out.println("after refresh carriers="+after+" display="+(visible==null?0:visible.elp())+" stat67="+actor.e(ffw.shA).aYS());
  if(before!=1||after!=1||visible==null||visible.elp()!=1)throw new AssertionError("state changed during snapshot");
  System.out.println("PASS: original big.a(snapshot,false) preserves actual carrier/display child");
 }
}
