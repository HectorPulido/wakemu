import java.lang.reflect.*;
/** Original eZR.aZB flag5 OR definition suppression; no replaced implementation. */
public final class ProbeNativeLevelOneSuppressionFlag {
 static class Runner extends eYg {
  void definition(boolean base, boolean flag){
   bfp=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
    if(m.getName().equals("aZB"))return base;
    if(m.getName().equals("a")&&a!=null&&a.length==1&&a[0] instanceof eVl)return flag&&a[0]==eVl.rwC;
    throw new UnsupportedOperationException(m.getName());
   });
  }
 }
 public static void main(String[]args)throws Exception {
  if(eVl.rwC.fLK()!=5)throw new AssertionError("native flag identity");
  for(Class<?> c:new Class<?>[]{eYg.class,eZC.class,eZB.class,eXD.class,eXK.class})
   if(c.getMethod("aZB").getDeclaringClass()!=eZR.class)throw new AssertionError("unexpected override "+c);
  Runner r=new Runner();
  for(boolean base:new boolean[]{false,true})for(boolean flag:new boolean[]{false,true}){
   r.definition(base,flag);if(r.aZB()!=(base||flag))throw new AssertionError("native OR");
  }
  System.out.println("PASS original flag5 identity/inheritance and eZR.aZB four-case OR");
 }
}
