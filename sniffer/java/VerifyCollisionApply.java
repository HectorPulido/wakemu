import java.lang.reflect.*;
public class VerifyCollisionApply {
 public static void main(String[]args)throws Exception {
  fff ap=new fff(ffw.sgD,0,Integer.MAX_VALUE);ap.or(6);ap.on(6);
  eVZ e=new eVZ(ffw.sgD);
  Field value=Qe.class.getDeclaredField("aSg");value.setAccessible(true);value.setInt(e,1);
  Method d=eVZ.class.getDeclaredMethod("d",PA.class);d.setAccessible(true);d.invoke(e,ap);
  if(ap.aYS()!=5||e.getValue()!=1)throw new AssertionError();
  ap.nG(e.getValue());if(ap.aYS()!=6)throw new AssertionError();
  System.out.println("Native eVZ.d AP6->5 actual1; native eWR restoration nG(actual) returns6");
 }
}
