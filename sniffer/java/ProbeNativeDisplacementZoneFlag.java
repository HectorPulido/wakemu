import java.lang.reflect.*;import java.util.*;
/** Native flag identity and eXK/eXJ endpoint equivalence with/without flag3. */
public class ProbeNativeDisplacementZoneFlag {
 static void set(Object o,Class<?>c,String name,Object value)throws Exception{Field f=c.getDeclaredField(name);f.setAccessible(true);f.set(o,value);}
 static PV actor(int x,int y){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class,fax.class},(p,m,a)->switch(m.getName()){case "bcz"->x;case "bcA"->y;case "bcB"->(short)0;case "bcy","baA"->aAS.wL(3);default->throw new UnsupportedOperationException(m.getName());});}
 static String endpoint(Class<?>type,boolean visual)throws Exception{
  Object runner=type.getConstructor().newInstance();set(runner,Qe.class,"bfr",actor(0,0));set(runner,Qe.class,"bfs",actor(4,0));set(runner,eXD.class,"ckD",3);
  eVn def=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->switch(m.getName()){case "fKJ"->1;case "a"->visual&&a[0]==eVl.rwA;default->throw new UnsupportedOperationException(m.getName());});set(runner,Qe.class,"bfp",def);
  Method method=type.getDeclaredMethod("fOu");method.setAccessible(true);aBn cell=(aBn)method.invoke(runner);return cell.getX()+","+cell.getY()+","+cell.bdn();
 }
 public static void main(String[]args)throws Exception{
  if(eVl.rwA.fLK()!=3||!eVl.rwA.name().equals("DONT_DISPLAY_ZONE"))throw new AssertionError();System.out.println("PASS native flag3="+eVl.rwA.name());
  for(Class<?>c:List.of(eXK.class,eXJ.class)){String plain=endpoint(c,false),flagged=endpoint(c,true);if(!plain.equals(flagged))throw new AssertionError();System.out.println("PASS "+c.getSimpleName()+" geometry unchanged="+plain);}
 }
}
