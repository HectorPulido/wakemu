import java.lang.reflect.*;
import java.util.*;
public class ProbeNativeAbsentGroupContainer {
 static void set(Object o,Class<?> owner,String name,Object value)throws Exception{Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(o,value);}
 static PV actor(long id){return(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},(p,m,a)->{if(m.getName().equals("Sn"))return id;throw new UnsupportedOperationException(m.getName());});}
 static eVv definition(int id){return(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class<?>[]{eVv.class},(p,m,a)->switch(m.getName()){
  case "aZE"->id;case "aZD"->(byte)2;case "aZA","cxq"->true;default->throw new UnsupportedOperationException(m.getName());});}
 static eVo container(){return(eVo)Proxy.newProxyInstance(eVo.class.getClassLoader(),new Class<?>[]{eVo.class},(p,m,a)->switch(m.getName()){
  case "aZY"->11;case "QF"->6266L;case "cmZ"->(short)200;default->throw new UnsupportedOperationException(m.getName());});}
 public static void main(String[]args)throws Exception{
  System.out.println("state_context="+HexFormat.of().formatHex(eVt.a(true,false,null).fLV().toByteArray()));
  for(eYg group:List.of(new eYg(),new eYw(),new eYm())){
   set(group,Qe.class,"bfx",901L);set(group,Qe.class,"bfy",800L);set(group,Qe.class,"bfp",definition(350552));set(group,Qe.class,"bfq",null);
   set(group,Qe.class,"bfr",actor(7));set(group,Qe.class,"bfs",actor(-7));set(group,Qe.class,"bft",new aBn(4,5,(short)0));
   System.out.println(group.getClass().getSimpleName()+" proto="+HexFormat.of().formatHex(group.bca().toByteArray()));
   eVt context=eVt.a(false,false,null);context.mb(false);context.SP(200);
   System.out.println("child_context="+HexFormat.of().formatHex(context.fLV().toByteArray()));
  }
 }
}
