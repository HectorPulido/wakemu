import java.lang.reflect.*;
import java.util.*;
/** Original acS instant-strategy clear leaves the run name unchanged; no client or UI. */
public class ProbeNativeInstantMovementStop {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 static Object get(Object o,Class<?> c,String n)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);return f.get(o);}
 public static void main(String[]args)throws Exception {
  Field u=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");u.setAccessible(true);
  acS actor=(acS)((sun.misc.Unsafe)u.get(null)).allocateInstance(acS.class);
  set(actor,YF.class,"bHP","AnimCourse02");
  set(actor,acS.class,"cjB",adB.bwx());set(actor,acS.class,"cjC",adf.bwn());
  set(actor,acS.class,"cjl",new ArrayList<>());set(actor,acS.class,"cjr",new amK(2));
  set(actor,acS.class,"cjv",false);
  adx original=actor.bvE();actor.a(adz.bwv());
  if(!(get(actor,acS.class,"cjC") instanceof adA))throw new AssertionError("instant stop strategy");
  actor.bvC();actor.a(original);
  if(get(actor,acS.class,"cjr")!=null||(boolean)get(actor,acS.class,"cjv")||!actor.bkG().equals("AnimCourse02"))throw new AssertionError("stationary running not reproduced");
  System.out.println("PASS original acS.a(adz) -> bvC -> restore strategy: path=null, moving=false, animation=AnimCourse02 unchanged");
 }
}
