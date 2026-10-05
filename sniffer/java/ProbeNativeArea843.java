import java.lang.reflect.*;import java.nio.file.*;import java.util.*;
/** Actual eXU/eYc parameter, explicit Qq selection and bcF guard. No render. */
public class ProbeNativeArea843 {
 static class Manager extends Qs {int calls; public Qq dp(long id){return null;} public void b(Qq q){calls++;}}
 static void set(Object o,String n,Object v)throws Exception{ProbeNativeSummonDescriptor.set(o,n,v);}
 public static void main(String[]args)throws Exception{
  eGM.a(null);
  for(int wanted:new int[]{-1,1474,1477})for(boolean removable:new boolean[]{false,true}){
   eXU r=new eXU();Manager manager=new Manager();ProbeNativeAreaCallbacks.Area area=new ProbeNativeAreaCallbacks.Area();
   set(area,"bgV",1474L);set(area,"aHm",901L);set(area,"bhh",removable);set(area,"bgX",new aBn(0,0,(short)0));
   PN context=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(o,m,a)->switch(m.getName()){
    case "baf"->manager;case "baa"->null;default->throw new UnsupportedOperationException(m.getName());});
   eVv def=(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(o,m,a)->switch(m.getName()){
    case "fLb"->false;case "aZE"->300001;case "fKJ"->1;case "a"->wanted;default->throw new UnsupportedOperationException(m.getName());});
   set(r,"bfw",context);set(r,"bfp",def);set(r,"bfs",area);set(r,"bfr",ProbeNativeEffectUIDs.actor(7));
   set(r,"bft",new aBn(0,0,(short)0));set(r,"bfD",true);set(r,"bfx",999L);set(r,"bfy",999L);
   r.C(null);Method apply=eYc.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(r,null,false);
   int expected=removable&&(wanted==-1||wanted==1474)?1:0;
   if(manager.calls!=expected)throw new AssertionError("native explicit Qq selection/bcF");
   if(expected==1&&args.length>0){set(r,"rEj",true);Files.write(Path.of(args[0]),r.bca().toByteArray());}
  }
  System.out.println("PASS original eXU/eYc explicit Qq filter + bcF six cases");
 }
}
