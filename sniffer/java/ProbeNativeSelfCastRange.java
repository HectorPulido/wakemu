import java.lang.reflect.*;
public class ProbeNativeSelfCastRange {
 public static void main(String[]args){
  PV actor=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
   if(m.getName().equals("bcz")||m.getName().equals("bcA"))return 0;
   throw new UnsupportedOperationException(m.getName());
  });
  fcj checker=new fcj(null);
  for(boolean allowed:new boolean[]{false,true})for(int x:new int[]{0,1,4}){
   boolean actual=checker.a(actor,null,1,3,allowed,x,0);
   boolean expected=(x>=1&&x<=3)||(x==0&&allowed);
   if(actual!=expected)throw new AssertionError("range/self mismatch");
  }
  System.out.println("PASS original fcj.a six range/self cases");
 }
}
