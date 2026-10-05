import java.lang.reflect.*;import java.util.*;
public class ProbeNativeIndirectTrigger {
 static void set(Object o,String n,Object v)throws Exception{for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(o,v);return;}catch(NoSuchFieldException e){}throw new NoSuchFieldException(n);}
 public static void main(String[]args)throws Exception{
  eOZ predicate=new eOZ(new ArrayList<alS>());
  eXE listener=new eXE();if(predicate.a(null,null,listener,null)!=-1)throw new AssertionError();
  int count=1;
  for(int kind:new int[]{0,1,3,11,12,25})for(boolean flag:new boolean[]{false,true}){
   eXE source=new eXE();set(source,"bfp",(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{if(m.getName().equals("a")&&a[0] instanceof eVl)return flag;throw new UnsupportedOperationException(m.getName());}));
   if(kind!=0)set(source,"bfq",(eVo)Proxy.newProxyInstance(eVo.class.getClassLoader(),new Class[]{eVo.class},(p,m,a)->{if(m.getName().equals("aZY"))return kind;throw new UnsupportedOperationException(m.getName());}));
   set(listener,"bfu",eVt.a(false,false,source));int expected=kind!=0&&kind!=11&&kind!=12&&!flag?0:-1;
   if(predicate.a(null,null,listener,null)!=expected)throw new AssertionError(kind+":"+flag);count++;
  }
  System.out.println("Original eOZ: source/null/PL kinds/REP34/arity "+count+" PASS");
 }
}
