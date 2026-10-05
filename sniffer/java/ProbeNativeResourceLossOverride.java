import java.lang.reflect.*;
/** eVZ.C -> eZR value override -> eWR.d, using the original native classes. */
public class ProbeNativeResourceLossOverride {
 public static void main(String[]args)throws Exception {
  eVZ effect=eVZ.a(null,ffw.sgD,VerifyCollisionAP.actor(0),VerifyCollisionAP.actor(100));
  // Suppress the secondary state: this probe isolates value ordering only.
  eVI.fMg().b(eVl.rwP);
  effect.b(eVI.fMg());effect.C(null);
  if(effect.getValue()!=0)throw new AssertionError("C must calculate zero");
  eVt context=new eVt();context.SQ(2);
  Method override=eZR.class.getDeclaredMethod("a",eVt.class);override.setAccessible(true);
  override.invoke(effect,context);
  if(effect.getValue()!=2)throw new AssertionError("SQ must follow C");
  fff ap=new fff(ffw.sgD,0,6);ap.or(6);ap.on(6);
  Method apply=eVZ.class.getDeclaredMethod("d",PA.class);apply.setAccessible(true);
  apply.invoke(effect,ap);
  if(ap.aYS()!=4||effect.getValue()!=2)throw new AssertionError("d must consume SQ2");
  System.out.println("Native eVZ C0 -> SQ2 -> AP6/4 actual2 PASS");
  context.SQ(-2);override.invoke(effect,context);
  ap.on(3);apply.invoke(effect,ap);
  if(ap.aYS()!=5||effect.getValue()!=-2)throw new AssertionError("negative SQ must add resource");
  ap.nG(effect.getValue());
  if(ap.aYS()!=3)throw new AssertionError("removal must consume signed actual delta");
  System.out.println("Native negative SQ-2 -> AP3/5 actual-2 -> removal AP3 PASS");
 }
}
