import java.util.*;
import java.lang.reflect.*;
/** Original eNh/eNi/ePd/ePc evaluation, offline and without a client launch. */
public class ProbeNativeActivationPredicates {
 static ArrayList<alS> args(long... values){ArrayList<alS> out=new ArrayList<>();for(long n:values)out.add(new alw(n));return out;}
 static void check(boolean value,String label){if(!value)throw new AssertionError(label);}
 public static void main(String[] argv)throws Exception {
  Field uf=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");uf.setAccessible(true);
  sun.misc.Unsafe u=(sun.misc.Unsafe)uf.get(null);
  ProbeNativeActiveSpell.Fight fight=(ProbeNativeActiveSpell.Fight)u.allocateInstance(ProbeNativeActiveSpell.Fight.class);
  check(!new eNh(args(4)).b(null,null,null,fight),"absent activation");
  check(!new eNi(args()).b(null,null,null,fight),"absent default spell");
  for(boolean stasis:new boolean[]{false,true}) {
   fight.active=(PZ)Proxy.newProxyInstance(fcS.class.getClassLoader(),new Class[]{fcS.class},(p,m,a)->{
    switch(m.getName()){case "ayn":return 42;case "baP":return 4;case "baR":return null;case "e":return stasis;default:throw new AssertionError(m);}
   });
   check(new eNh(args(stasis?6:4)).b(null,null,null,fight),"native element/stasis");
   check(!new eNh(args(stasis?4:6)).b(null,null,null,fight),"stasis overrides element");
   check(new eNi(args(42)).b(null,null,null,fight),"actual activation ID");
   check(new eNi(args(4294967338L)).b(null,null,null,fight),"long to int narrowing");
   check(!new eNi(args()).b(null,null,null,fight),"null activation container");
  }
  eVZ source=new eVZ(), listener=new eVZ();
  Field parent=eZR.class.getDeclaredField("rIV");parent.setAccessible(true);parent.set(listener,source);
  check(!new ePd(args()).b(null,null,listener,null),"null definition");
  for(int variant:new int[]{0,1,2,3,-1}) {
   source.b((eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
    if(m.getName().equals("dd"))return (variant & ((Long)a[0]))!=0;throw new AssertionError(m);
   }));
   check(new ePd(args()).b(null,null,listener,null)==((variant&1)!=0),"critical variant "+variant);
  }
  for(byte status:new byte[]{-1,0,7,8}){source.fc(status);check(new ePc(args()).b(null,null,listener,null)==(status==7),"status "+status);}
  check(!new ePc(args()).b(null,null,null,null),"absent trigger");
  System.out.println("PASS native activation ID/element/stasis/narrowing and triggering variant/status");
 }
}
