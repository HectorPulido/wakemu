import java.lang.reflect.*;
/** Original eXv.fOC with explicit characteristic authority and eVt. */
public class ProbeNativeLifeSteal {
 static void set(Object o,String name,Object value)throws Exception {Class<?> c=o.getClass();while(c!=null){try{Field f=c.getDeclaredField(name);f.setAccessible(true);f.set(o,value);return;}catch(NoSuchFieldException e){c=c.getSuperclass();}}throw new NoSuchFieldException(name);}
 static PV actor(ffw stat,int value){return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{if(m.getName().equals("a")&&a!=null&&a[0] instanceof PC)return a[0]==stat;if(m.getName().equals("c"))return value;throw new UnsupportedOperationException(m.getName());});}
 public static void main(String[]args)throws Exception{
  for(int[]r:new int[][]{{10,50,200,0,1,12},{1,50,0,0,1,1},{7,50,100,4,1,5},{7,50,100,4,0,3},{10,0,1200,0,1,0}}){
   eXv e=new eXv();eVt context=new eVt();context.SQ(r[3]);set(e,"aSg",r[0]);set(e,"bfr",actor(ffw.shm,r[1]));set(e,"bfs",actor(ffw.sha,r[2]));set(e,"bfu",context);set(e,"rDE",r[4]==1);e.fOC();
   if(e.getValue()!=r[5]||context.Ol()!=r[5])throw new AssertionError("native eXv amount="+e.getValue()+" expected="+r[5]);
  }
  if(args.length>0){eXv e=new eXv();eVj entry=null;for(Field f:eVi.class.getDeclaredFields())if(f.getType()==eVj.class){eVj x=(eVj)f.get(null);if(x.d()==24)entry=x;}
   if(entry==null||entry.bkv().getClass()!=eXv.class)throw new AssertionError("registry24");
   System.out.println("registry24 eXv; LIFE_STOLEN_BONUS53 RES_HEAL_PER_THOUSAND32");}
  eXv events=new eXv();events.bby();
  if(!events.bbw().equals(java.util.BitSet.valueOf(new long[]{(1L<<0)|(1L<<1)|(1L<<20)})))
   throw new AssertionError("native no-container eXv events "+events.bbw());
  System.out.println("PASS original eXv arithmetic/context and null-container events0/1/20");
 }
}
