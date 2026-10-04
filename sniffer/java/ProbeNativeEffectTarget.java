import java.lang.reflect.*;import java.util.*;
public class ProbeNativeEffectTarget {
 static eHg actor(long id){return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class[]{eHg.class},(p,m,a)->{if(m.getName().equals("Sn"))return id;throw new UnsupportedOperationException(m.getName());});}
 public static void main(String[]args){eKb criterion=new eKb(new ArrayList<>());eHg caster=actor(7),target=actor(-8);
 if(criterion.d(caster,target,null,null)!=-8||criterion.d(caster,actor(99),null,null)!=99||criterion.d(caster,null,null,null)!=0)throw new AssertionError("target binding/null");
 System.out.println("PASS eKb/eII.b: target Sn differs from caster, rebounds99, null0");}
}
