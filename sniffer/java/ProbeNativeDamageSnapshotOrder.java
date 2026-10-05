import java.nio.file.*;
import java.lang.reflect.*;
/** Actual bje characteristics plus original cuU12873 and eXt resource consumption. */
public final class ProbeNativeDamageSnapshotOrder {
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Method convert=bbo.class.getDeclaredMethod("a",aMb.class,short.class);convert.setAccessible(true);
  blj[] profile=new blj[1];
  apw.bGL().a(new aMb(),new apB<aMb>(){public void load(aMb r){if(r.d()==1153)try{profile[0]=(blj)convert.invoke(null,r,(short)1153);}catch(Exception e){throw new RuntimeException(e);}}});
  bje target=bje.dsi();target.dA(-1327963637103750234L);target.c(profile[0]);target.bz((short)72);target.dpQ();
  Method prepare=bje.class.getDeclaredMethod("drd");prepare.setAccessible(true);prepare.invoke(target);
  target.e(ffw.sgC).on(86);
  cuU packet=new cuU();packet.dp(Files.readAllBytes(Path.of(args[0])));if(packet.KU()!=-1327963637103750234L)throw new AssertionError("cuU actor");
  // Decode original descriptor without graphical callbacks. Apply its native
  // characteristic section to the actual actor's ffh manager.
  eHd descriptor=new eHj();descriptor.ew(packet.aLJ());
  Method select=eHd.class.getDeclaredMethod("a",eHe.class);select.setAccessible(true);
  boolean installed=false;ffh decoded=null;
  for(eHf group:eHf.values())for(eHe field:group.fuK()) {
   gp part=(gp)select.invoke(descriptor,field);
   if(part instanceof pl section && section.SS!=null) {
    ffh candidate=new ffh();
    if(candidate.b(section.SS)&&candidate.e(ffw.sgC).aYS()==15) {
     target.frm().a(candidate);installed=true;decoded=candidate;
    }
   }
  }
  if(!installed)throw new AssertionError("Native HP15 section missing");
  int snapshotHP=target.c(ffw.sgC);
  eXt damage=new eXt();Method consume=eXt.class.getDeclaredMethod("a",int.class,PV.class,PV.class);consume.setAccessible(true);
  consume.invoke(damage,71,target,target);
  int actual=target.c(ffw.sgC);
  System.out.println("Native snapshotHP="+snapshotHP+" afterDamage71="+actual);
  if(snapshotHP!=15||actual!=0)throw new AssertionError("Expected final snapshot15 then clamped damage0");
  target.e(ffw.sgC).on(86);
  consume.invoke(new eXt(),71,target,target);
  if(target.c(ffw.sgC)!=15)throw new AssertionError("damage-first native HP");
  target.frm().a(decoded);
  if(target.c(ffw.sgC)!=15)throw new AssertionError("damage-first then snapshot");
  System.out.println("PASS control damage86-71=15 then native final snapshot15 preserves15");
 }
}
