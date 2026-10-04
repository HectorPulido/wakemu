import java.lang.reflect.*;
import java.util.*;
public class ProbeNativeDispel {
 static class Manager extends Qf {
  final List<Qe> effects=new ArrayList<>(); final List<Qe> removed=new ArrayList<>();
  public Qi bci(){return null;} public Iterator<Qe> iterator(){return effects.iterator();}
  public boolean q(Qe effect){removed.add(effect);return true;}
 }
 static void set(Object o,Class<?> owner,String name,Object value)throws Exception{Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(o,value);}
 static eVv definition(int generic,int action,int kind,boolean dispellable,int[]parameters){
  return(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class<?>[]{eVv.class},(p,m,a)->switch(m.getName()){
   case "aZE"->generic;case "awM"->action;case "aZD"->(byte)kind;case "cxq"->dispellable;
   case "fKJ"->parameters.length;case "a"->parameters[(int)a[0]];
   default->throw new UnsupportedOperationException(m.getName());});
 }
 static PL container(int kind){return(PL)Proxy.newProxyInstance(PL.class.getClassLoader(),new Class<?>[]{PL.class},(p,m,a)->{
  if(m.getName().equals("aZY"))return kind;throw new UnsupportedOperationException(m.getName());});}
 static PV target(Manager manager){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},(p,m,a)->{
  if(m.getName().equals("bax"))return manager;throw new UnsupportedOperationException(m.getName());});}
 public static void main(String[]args)throws Exception{
  Method eligible=eXe.class.getDeclaredMethod("E",Qe.class);eligible.setAccessible(true);
  for(int container:new int[]{0,1,3,11,12})for(boolean dispellable:new boolean[]{false,true}){
   eXE child=new eXE();set(child,Qe.class,"bfp",definition(123,400,2,dispellable,new int[]{}));
   set(child,Qe.class,"bfq",container==0?null:container(container));
   System.out.println("type2,cxq="+dispellable+",container="+container+" -> "+eligible.invoke(new eXe(),child));
  }
  Method execute=eXe.class.getDeclaredMethod("c",Qe.class,boolean.class);execute.setAccessible(true);
  for(int[]parameters:new int[][]{{},{123},{400,999},{456}}){
   Manager manager=new Manager();eXE child=new eXE();set(child,Qe.class,"bfp",definition(123,400,2,false,new int[]{}));manager.effects.add(child);
   eXe dispel=new eXe();set(dispel,Qe.class,"bfp",definition(999,421,2,true,parameters));set(dispel,Qe.class,"bfs",target(manager));
   execute.invoke(dispel,null,false);System.out.println("parameters="+Arrays.toString(parameters)+",protectedMatchRemoved="+manager.removed.size());
  }
 }
}
