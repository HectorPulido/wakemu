import java.lang.reflect.*;
public class ProbeNativeTriggerCaster {
 static void set(Object o, Class<?> c, String n, Object v) throws Exception {Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[] args) throws Exception {
  eKl getter=new eKl("triggeringCaster");
  if(getter.d(null,null,null,null)!=-1)throw new AssertionError("null source");
  eXE source=new eXE(), listener=new eXE();
  set(listener,Qe.class,"bfu",eVt.a(false,false,source));
  if(getter.d(null,null,listener,null)!=-1)throw new AssertionError("null caster");
  eHg caster=(eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class[]{eHg.class,PV.class},(p,m,a)->{if(m.getName().equals("Sn"))return -99L;throw new UnsupportedOperationException(m.getName());});
  set(source,Qe.class,"bfr",caster);
  if(getter.d(null,null,listener,null)!=-99)throw new AssertionError("source actor identity");
  eLN targetGetter=new eLN(new java.util.ArrayList<alS>());
  if(targetGetter.d(null,null,null,null)!=-1)throw new AssertionError("absent target source");
  set(source,Qe.class,"bfs",caster);
  if(targetGetter.d(null,null,listener,null)!=-1)throw new AssertionError("eHg proxy is not eGj");
  Field uf=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");uf.setAccessible(true);
  sun.misc.Unsafe unsafe=(sun.misc.Unsafe)uf.get(null);
  ProbeNativeLevelGroup.Actor target=(ProbeNativeLevelGroup.Actor)unsafe.allocateInstance(ProbeNativeLevelGroup.Actor.class);
  set(target,eGj.class,"aHm",12345L);set(source,Qe.class,"bfs",target);
  if(targetGetter.d(null,null,listener,null)!=12345L)throw new AssertionError("real eGj target");
  System.out.println("PASS native eKl: absent source/caster -1; triggering caster signed identity -99; eLN null/non-eGj -1 and eGj12345");
 }
}
