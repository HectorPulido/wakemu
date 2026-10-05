import java.lang.reflect.*;
public class ProbeNativeHealingFlags {
 static Object definition(int flag)throws Exception {
  Class<?> flags=Class.forName("eVl");Object chosen=null;
  for(Object v:flags.getEnumConstants()){Method id=flags.getMethod("fLK");if(((Number)id.invoke(v)).intValue()==flag)chosen=v;}
  final Object selected=chosen;
  return Proxy.newProxyInstance(Class.forName("eVn").getClassLoader(),new Class[]{Class.forName("eVn")},(p,m,a)->{
   if(m.getName().equals("a")&&a!=null&&a.length==1&&a[0].getClass()==flags)return a[0]==selected;
   if(m.getReturnType()==boolean.class)return false;
   if(m.getReturnType()==int.class)return 0;
   if(m.getReturnType()==short.class)return(short)0;
   return null;
  });
 }
 static void pk(Object runner,Object pk)throws Exception {
  Class<?> c=runner.getClass();while(c!=null){try{Field f=c.getDeclaredField("bfp");f.setAccessible(true);f.set(runner,pk);return;}catch(NoSuchFieldException e){c=c.getSuperclass();}}
 }
 public static void main(String[] a)throws Exception{
  Constructor<?> h=Class.forName("eXs").getDeclaredConstructor();h.setAccessible(true);Object heal=h.newInstance();
  Method gate=Class.forName("eZR").getDeclaredMethod("bcd");gate.setAccessible(true);
  pk(heal,definition(15));if(!Boolean.TRUE.equals(gate.invoke(heal)))throw new AssertionError("KO flag15");
  Constructor<?> d=Class.forName("eXt").getDeclaredConstructor();d.setAccessible(true);Object damage=d.newInstance();Method direct=damage.getClass().getDeclaredMethod("fOG");direct.setAccessible(true);
  pk(damage,definition(34));if(!Boolean.FALSE.equals(direct.invoke(damage)))throw new AssertionError("direct34");
  System.out.println("PASS native eZR KO gate15 and eXt direct34");
 }
}
