import java.lang.reflect.*;
/** Original eVZ/eWW amount mutation around application; no second C call. */
public class ProbeNativeResourceLossTriggerValue {
 public static void main(String[]args)throws Exception {
  eVZ r=eVZ.a(null,ffw.sgD,VerifyCollisionAP.actor(0),VerifyCollisionAP.actor(100));
  eVI.fMg().b(eVl.rwP); // Native flag19 suppresses5227 in this isolated PA probe.
  r.b(eVI.fMg());r.C(null);
  eVt context=new eVt();context.SQ(2);
  Method override=eZR.class.getDeclaredMethod("a",eVt.class);override.setAccessible(true);
  override.invoke(r,context);
  r.a(1,1f,false); // L2 source2 ->3
  fff ap=new fff(ffw.sgD,0,6);ap.or(6);ap.on(6);
  Method apply=eVZ.class.getDeclaredMethod("d",PA.class);apply.setAccessible(true);
  apply.invoke(r,ap);
  if(ap.aYS()!=3||r.getValue()!=3||r.Mt()!=0)throw new AssertionError("L2 amount consumed/origin");
  r.a(1,1f,false); // L3 modifies amount without reapplying PA.
  if(ap.aYS()!=3||r.getValue()!=4)throw new AssertionError("L3 must not reapply");
  ap.on(1);Method remove=eWR.class.getDeclaredMethod("fNM");remove.setAccessible(true);
  // Original removal needs its target PA. Direct PA.nG is exact fNM operation.
  ap.nG(r.getValue());
  if(ap.aYS()!=5)throw new AssertionError("retirement live amount4");
  System.out.println("PASS eVZ L2 amount3 consumes3; L3 amount4 leavesPA3; retirement adds4; Mt0");
 }
}
