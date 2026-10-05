import java.lang.reflect.*;
/** Original eXt calculation and gates with visual DONT_DISPLAY_ZONE flag. */
public class ProbeNativeDamageZoneFlag {
 static class Runner extends eXt {
  void definition(boolean flagged){
   bfp=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
    (p,m,a)->{
     if(m.getName().equals("a")&&a.length==1&&a[0] instanceof eVl)return flagged&&a[0]==eVl.rwA;
     if(m.getName().equals("a")&&a.length==3)return 37;
     if(m.getName().equals("fKJ"))return 1;
     throw new UnsupportedOperationException(m.getName());
    });
  }
 }
 static Object call(Runner r,String name)throws Exception{Method m=eXt.class.getDeclaredMethod(name);m.setAccessible(true);return m.invoke(r);}
 public static void main(String[]args)throws Exception{
  if(eVl.rwA.fLK()!=3||!eVl.rwA.name().equals("DONT_DISPLAY_ZONE"))throw new AssertionError();
  Runner plain=new Runner(),flagged=new Runner();plain.definition(false);flagged.definition(true);
  call(plain,"fOA");call(flagged,"fOA");
  if(plain.getValue()!=37||flagged.getValue()!=plain.getValue())throw new AssertionError("calculation");
  for(String name:new String[]{"fOG","fOI","bbA","bbB","bcd"})
   if(!call(plain,name).equals(call(flagged,name)))throw new AssertionError(name);
  System.out.println("Native eXt flag3 identity, parameter calculation and five gates unchanged: 7 PASS");
 }
}
