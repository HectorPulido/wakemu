import java.lang.reflect.*;
/** Real eXt override, independent of spell, damage element or critical branch. */
public class ProbeNativeDamageKoFlag {
 static class Runner extends eXt {
  void definition(boolean flagged){
   bfp=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
    (p,m,a)->{if(m.getName().equals("a")&&a!=null&&a.length==1&&a[0] instanceof eVl)
      return flagged&&a[0]==eVl.rwL;
      throw new UnsupportedOperationException(m.getName());});
  }
  boolean allowsKo(){return bcd();}
 }
 public static void main(String[]args){
  Runner runner=new Runner();runner.definition(false);
  if(!runner.allowsKo())throw new AssertionError("unflagged override");
  runner.definition(true);
  if(!runner.allowsKo())throw new AssertionError("flagged override");
  System.out.println("Native eXt.bcd flagged/unflagged both true: 2 PASS");
 }
}
