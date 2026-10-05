import java.lang.reflect.*;
/** eVZ.C keeps its original raw-1 upper bound after copying a source value. */
public class ProbeNativeResourceLossCopy {
 static void set(Object object,String name,Object value)throws Exception {
  Class<?> owner=object.getClass();
  while(owner!=null){try{Field field=owner.getDeclaredField(name);field.setAccessible(true);field.set(object,value);return;}catch(NoSuchFieldException e){owner=owner.getSuperclass();}}
  throw new NoSuchFieldException(name);
 }
 static PV actor(){return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
  if(m.getReturnType()==boolean.class)return false;
  if(m.getReturnType()==int.class)return 0;
  if(m.getReturnType()==long.class)return 0L;
  return null;
 });}
 public static void main(String[]args)throws Exception {
  eVZ source=new eVZ(ffw.sgD);set(source,"aSg",2);
  eVZ loss=new eVZ(ffw.sgE);set(loss,"bfp",eVR.j(new float[]{-1,0},1000));
  set(loss,"bfr",actor());set(loss,"bfs",actor());loss.C(source);
  if(loss.getValue()!=-1||loss.Mt()!=0)throw new AssertionError("Original raw-1 bound lost");
  System.out.println("PASS eVZ.C raw-1/source2 -> rounded1 -> native GS upper-1 -> value-1, Mt0");
 }
}
