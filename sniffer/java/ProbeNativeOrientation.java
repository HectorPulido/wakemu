import java.lang.reflect.*;
import java.util.*;

/** Execute original eWF.C/c with explicit PV holders, including rebind/property. */
public class ProbeNativeOrientation {
 static class Holder implements InvocationHandler {
  int x,y;short z; aAS direction;boolean locked;
  Holder(int x,int y,int direction){this.x=x;this.y=y;this.direction=aAS.wL(direction);}
  PV pv(){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},this);}
  public Object invoke(Object p,Method m,Object[]a){return switch(m.getName()){
   case "bcz"->x;case "bcA"->y;case "bcB"->z;case "bcy"->direction;
   case "a"->{if(a[0] instanceof aAS){direction=(aAS)a[0];yield null;}yield locked;}
   default->throw new UnsupportedOperationException(m.getName());};}
 }
 static void check(int mode,int sourceDir,int targetDir,boolean locked,int expected,boolean casterRebound)throws Exception{
  Holder caster=new Holder(0,0,sourceDir),target=new Holder(3,2,targetDir);
  target.locked=locked;
  PV c=caster.pv(),t=target.pv();eWF runner=new eWF();
  eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
   (p,m,a)->{if(m.getName().equals("a")&&a.length==3)return mode;throw new UnsupportedOperationException(m.getName());});
  for(String name:new String[]{"bfp","bfr","bfs"}){Field f=Qe.class.getDeclaredField(name);f.setAccessible(true);f.set(runner,name.equals("bfp")?definition:name.equals("bfr")?c:t);}
  runner.c(4,0,(short)0);runner.C(null);
  Method apply=eWF.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(runner,null,true);
  int actual=(casterRebound?caster:target).direction.wp();
  if(actual!=expected||((runner.bbc()==c)!=casterRebound))throw new AssertionError(mode+" actual="+actual+" expected="+expected);
 }
 public static void main(String[]args)throws Exception{
  check(0,1,7,false,7,false);check(1,1,7,false,5,false);check(2,1,3,false,7,false);
  check(3,5,7,false,1,false);check(4,1,7,false,3,false);check(6,2,7,false,2,false);
  check(7,2,7,false,6,false);check(8,7,5,false,1,true);check(8,7,5,true,1,true);check(9,1,7,false,5,false);
  check(10,1,7,false,3,false);check(11,1,7,false,3,false);check(1,1,7,true,7,false);
  System.out.println("Native eWF modes0..11 (random excluded), rebind and sev lock:13PASS");
 }
}
