import java.lang.reflect.*;import java.util.*;
/** Actual eWh/eWi source listener updates, clamping and removal. */
public class ProbeNativeCharacteristicLink {
 static void set(Object o,Class<?> owner,String field,Object value)throws Exception{Field f=owner.getDeclaredField(field);f.setAccessible(true);f.set(o,value);}
 public static void main(String[]args)throws Exception{
  ffw sourceID=ffw.fK((byte)7),targetID=ffw.fK((byte)103);
  fff source=new fff(sourceID,0,1000),target=new fff(targetID,0,1000);
  source.or(1000);source.on(60);target.or(1000);target.on(10);
  PV actor=ProbeCombatArithmetic.actor(new HashMap<>(Map.of(sourceID,source,targetID,target)),7);
  eWh runner=new eWh();set(runner,Qe.class,"bfr",actor);set(runner,Qe.class,"bfs",actor);set(runner,Qe.class,"aSg",7);
  set(runner,eWa.class,"rAm",103);runner.rAE=50;runner.rAF=0;runner.rAG=Integer.MIN_VALUE;
  Method apply=eWa.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(runner,null,true);
  if(target.aYS()!=40)throw new AssertionError("initial link");
  source.nG(20);if(target.aYS()!=50)throw new AssertionError("source callback update");
  source.oo(60);if(target.aYS()!=20)throw new AssertionError("source decrease replace previous contribution");
  Field observer=eWa.class.getDeclaredField("rAo");observer.setAccessible(true);eWb listener=(eWb)observer.get(runner);
  listener.cancel();listener.bLM();if(target.aYS()!=10)throw new AssertionError("cancel contribution");
  source.nG(20);if(target.aYS()!=10)throw new AssertionError("detach listener");
  System.out.println("PASS real eWh initial40/sourceup50/sourcedown20/cancel10/detach10");
 }
}
