import java.lang.reflect.*;
/** Original eWK.C/c and Qe.f over real runner storage, without catalogs. */
public class ProbeNativeRedirectRunner1000 {
 static Field field(Object object,String name)throws Exception {
  for(Class<?> type=object.getClass();type!=null;type=type.getSuperclass()) {
   try {Field f=type.getDeclaredField(name);f.setAccessible(true);return f;}
   catch(NoSuchFieldException ignored){}
  }throw new NoSuchFieldException(name);
 }
 static void set(Object o,String n,Object v)throws Exception {field(o,n).set(o,v);}
 static Object get(Object o,String n)throws Exception {return field(o,n).get(o);}
 static PV actor(){return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},
  (p,m,a)->{throw new UnsupportedOperationException(m.getName());});}
 public static void main(String[]args)throws Exception {
  Method apply=eWK.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);
  int assertions=0;
  for(int mode:new int[]{0,1,2})for(int ratio:new int[]{-1,0,100}){
   eWK listener=new eWK(); PV caster=actor(),target=actor(),previous=actor();
   eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},
    (p,m,a)->{if(m.getName().equals("fKJ"))return 2;
     if(m.getName().equals("a"))return ((Integer)a[0])==0?ratio:mode;
     throw new UnsupportedOperationException(m.getName());});
   set(listener,"bfp",definition);set(listener,"bfr",caster);set(listener,"bfs",target);
   set(listener,"bfD",true);listener.C(null);
   if(listener.getValue()!=ratio)throw new AssertionError("C ratio");assertions++;
   eYx source=new eYx();aBn anchor=new aBn(7,8,(short)9);
   set(source,"bfr",previous);set(source,"bfs",previous);set(source,"bft",anchor);
   apply.invoke(listener,source,false);
   if(get(source,"bfs")!=(mode==1?target:caster)||get(source,"bfr")!=previous
      ||get(source,"bft")!=anchor)throw new AssertionError("Qe target identity");assertions++;
   set(source,"bfs",previous);set(listener,"bfD",false);apply.invoke(listener,source,false);
   if(get(source,"bfs")!=previous)throw new AssertionError("bbs guard");assertions++;
  }
  System.out.println("PASS original eWK1000: 9 mode/ratio cases, "+assertions+" assertions");
 }
}
