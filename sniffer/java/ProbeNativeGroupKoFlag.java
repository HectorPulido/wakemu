import java.lang.reflect.*;
/** Native eZR.bcd flag15 bypass, independent of group/spell identity. */
public class ProbeNativeGroupKoFlag {
 static class Runner extends eYg {
  void definition(boolean permitted){
   bfp=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
    if(m.getName().equals("a")&&a!=null&&a.length==1&&a[0] instanceof eVl)
     return permitted&&a[0]==eVl.rwL;
    throw new UnsupportedOperationException(m.getName());
   });
  }
  boolean allowsKo(){return bcd();}
 }
 public static void main(String[]args){
  Runner runner=new Runner();runner.definition(true);
  if(!runner.allowsKo())throw new AssertionError("flag15 must permit KO");
  runner.definition(false);
  if(!runner.allowsKo())throw new AssertionError("eYg override permits KO even without flag15");
  System.out.println("Native eYg.bcd flagged/unflagged KO permission PASS");
 }
}
