import java.lang.reflect.*;import java.util.*;
public class ProbeNativeZoneTrigger {
 static class Runner extends eYg {
  void definition(boolean flag,anc area){bfp=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->switch(m.getName()){
   case"a"->flag&&a[0]==eVl.rwB;case"aZP"->area;default->throw new UnsupportedOperationException(m.getName());});}
 }
 public static void main(String[]args){
  ePb criterion=new ePb(new ArrayList<>());Runner listener=new Runner();
  if(criterion.b(null,null,listener,null))throw new AssertionError("Absentsource");
  Runner source=new Runner();listener.a(eVt.a(true,false,source));
  if(criterion.b(null,null,listener,null))throw new AssertionError("Null definition");
  for(boolean flag:new boolean[]{false,true})for(anc area:List.of(anD.bEz(),new anG())){
   source.definition(flag,area);boolean expected=flag||area.bEk()!=and.cIO;
   if(criterion.b(null,null,listener,null)!=expected)throw new AssertionError("flag/area mismatch");
  }
  System.out.println("Native ePb/amb nullsource/nullPK/flag/area PASS");
 }
}
