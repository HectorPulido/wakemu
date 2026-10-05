import java.util.ArrayList;
public class ProbeNativeConditionLOS {
 public static void main(String[] args) throws Exception {
  eMr condition=new eMr(new ArrayList<alS>());
  if(condition.a(null,null,null,null)!=-1)throw new AssertionError("native missing context false");
  eOq off=new eOq(new ArrayList<alS>());
  if(off.a(null,null,null,null)!=-1)throw new AssertionError("native missing offplay actor false");
  for(boolean value:new boolean[]{false,true}){
   Object actor=java.lang.reflect.Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class[]{eHg.class},(p,m,a)->{
    if(m.getName().equals("baG"))return value;
    if(m.getReturnType()==boolean.class)return false;
    if(m.getReturnType()==int.class)return 0;
    if(m.getReturnType()==long.class)return 0L;
    if(m.getReturnType()==byte.class)return(byte)0;
    if(m.getReturnType()==short.class)return(short)0;
    return null;
   });
   if(off.a(actor,null,null,null)!=(value?0:-1))throw new AssertionError("native baG");
  }
  System.out.println("PASS eMr missing caster/map false and eOq baG true/false");
 }
}
