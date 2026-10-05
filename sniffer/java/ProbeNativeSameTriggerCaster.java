import java.lang.reflect.*;
import java.util.ArrayList;
public class ProbeNativeSameTriggerCaster {
 static void set(Object o,String n,Object v)throws Exception {Field f=Qe.class.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[] a)throws Exception {
  eLL criterion=new eLL(new ArrayList<alS>());
  PV first=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,args)->{throw new UnsupportedOperationException(m.getName());});
  PV second=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,args)->{throw new UnsupportedOperationException(m.getName());});
  eXE listener=new eXE(), source=new eXE();
  if(criterion.a(null,null,listener,null)!=0)throw new AssertionError("both null");
  set(listener,"bfr",first);
  if(criterion.a(null,null,listener,null)!=-1)throw new AssertionError("absent source");
  set(listener,"bfu",eVt.a(false,false,source));set(source,"bfr",first);
  if(criterion.a(null,null,listener,null)!=0)throw new AssertionError("same object");
  set(source,"bfr",second);
  if(criterion.a(null,null,listener,null)!=-1)throw new AssertionError("different object");
  set(source,"bfr",null);
  if(criterion.a(null,null,listener,null)!=-1)throw new AssertionError("null source caster");
  boolean failed=false;try{criterion.a(null,null,null,null);}catch(alA e){failed=true;}
  if(!failed)throw new AssertionError("non runner must reject");
  System.out.println("PASS eLL: null pair, absent source, same object, different object, null source caster, non-Qe error");
 }
}
