/** Actual Qq.a charge/reentry/null-target gate, native faZ/faY bcv/e/c. */
public class ProbeNativeAreaActivationCharges {
 static Qu callbacks=(Qu)java.lang.reflect.Proxy.newProxyInstance(Qu.class.getClassLoader(),new Class[]{Qu.class},(p,m,a)->null);
 static class Hour extends faZ {
  public java.util.List<amP> d(amP target){return n(target);}
  protected Qq bcs(){return new Hour();}public int aeV(){return 0;}public int df(long id){return 0;}
  public byte bav(){return 0;}public byte[] baz(){return new byte[0];}public anS bEs(){return null;}
  Hour(PV owner){bgZ=owner;bfB=1;a(callbacks);}Hour(){}
 }
 static class Glyph extends faY {
  public java.util.List<amP> d(amP target){return n(target);}
  protected Qq bcs(){return new Glyph();}public int aeV(){return 0;}public int df(long id){return 0;}
  public byte bav(){return 0;}public byte[] baz(){return new byte[0];}public anS bEs(){return null;}
  public void a(int x,int y,short z,Qe source){}
  Glyph(){bfB=1;a(callbacks);}
 }
 public static void main(String[]args){
  PV owner=ProbeNativeEffectUIDs.actor(7);Hour hour=new Hour(owner);
  if(hour.a((Qe)null,null)||!hour.a((Qe)null,owner)||!hour.a((Qe)null,owner)||hour.bfB!=1)throw new AssertionError("native HOUR charges/null");
  Glyph glyph=new Glyph();if(!glyph.a((Qe)null,owner)||glyph.bfB!=0||glyph.a((Qe)null,owner))throw new AssertionError("native GLYPH charges");
  Glyph removed=new Glyph();if(!removed.a((Qe)null,null)||removed.bfB!=0)throw new AssertionError("native glyph null activation");
  System.out.println("PASS native HOUR retains finite charge; GLYPH consumes; null HOURreject/GLYPHno coordinates");
 }
}
