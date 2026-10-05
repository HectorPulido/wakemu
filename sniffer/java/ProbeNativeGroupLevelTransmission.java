import java.lang.reflect.*;
/** Real eZR.fRR: inherited eVt override, native short cast, PL/null fallback. */
public class ProbeNativeGroupLevelTransmission {
 static Field field(String name)throws Exception{Field f=Qe.class.getDeclaredField(name);f.setAccessible(true);return f;}
 public static void main(String[]args)throws Exception{
  eYg runner=new eYg();
  field("bfq").set(runner,Proxy.newProxyInstance(eVo.class.getClassLoader(),new Class[]{eVo.class},(p,m,a)->{
   if(m.getName().equals("cmZ"))return(short)200;throw new UnsupportedOperationException(m.getName());}));
  if(runner.fRR()!=200)throw new AssertionError();
  eVt parent=new eVt();parent.SP(65538);field("bfu").set(runner,parent);
  if(runner.fRR()!=2)throw new AssertionError();
  parent.SP(-1);if(runner.fRR()!=200)throw new AssertionError();
  // eYg.d builds a fresh PS: it must not inherit the source runner's SP.
  parent.SP(200);
  eVt child=runner.d(runner,false);
  if(child.Oh()!=-1)throw new AssertionError("Child PS inherited parent SP");
  field("bfq").set(runner,Proxy.newProxyInstance(eVo.class.getClassLoader(),new Class[]{eVo.class},(p,m,a)->{
   if(m.getName().equals("cmZ"))return(short)10;throw new UnsupportedOperationException(m.getName());}));
  field("bfu").set(runner,child);
  if(runner.fRR()!=10)throw new AssertionError("Child did not reset to actual PL10");
  field("bfq").set(runner,null);if(runner.fRR()!=0)throw new AssertionError();
  System.out.println("Native eZR.fRR priority/short cast, new child SP reset/PL10/null0 PASS");
 }
}
