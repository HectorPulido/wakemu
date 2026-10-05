import java.lang.reflect.*;
public class ProbeNativeCorpseGroup{
 static class Runner extends eYg{void target(PV p){bfs=p;}boolean bypass(){return bcd();}}
 public static void main(String[]args){
  for(boolean corpse:new boolean[]{false,true}){
   PV target=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
    if(m.getName().equals("baG"))return corpse;
    throw new UnsupportedOperationException(m.getName());
   });Runner r=new Runner();r.target(target);
   if(!r.bypass()||!r.i(null))throw new AssertionError("eYg must bypass original corpse gate");
  }
  System.out.println("PASS native eYg.bcd/eZR.i alive and corpse");
 }
}
