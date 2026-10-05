import java.lang.reflect.*;import java.util.*;
public class ProbeNativeSourceREP {
 static void set(Object o,Class<?> c,String n,Object v)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 static eOY criterion(long flag){ArrayList<alS> args=new ArrayList<>();args.add(new alw(flag));return new eOY(args);}
 public static void main(String[] args)throws Exception{
  eXE source=new eXE(),listener=new eXE();set(listener,Qe.class,"bfu",eVt.a(false,false,source));
  final eVl flag28=eVl.SM(28);
  eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{if(m.getName().equals("a")&&a.length==1&&a[0] instanceof eVl)return a[0]==flag28;throw new UnsupportedOperationException(m.getName());});
  set(source,Qe.class,"bfp",definition);
  if(criterion(28).a(null,null,listener,null)!=0)throw new AssertionError("flag present");
  if(criterion(4).a(null,null,listener,null)!=-1)throw new AssertionError("flag absent");
  if(criterion(28).a(null,null,null,null)!=-1)throw new AssertionError("source null");
  if(criterion((1L<<32)+28).a(null,null,listener,null)!=0)throw new AssertionError("long to int");
  System.out.println("PASS eOY sourceREP true/false/null/long-int; nativeflags="+Arrays.toString(Arrays.stream(eVl.values()).mapToInt(eVl::fLK).toArray()));
 }
}
