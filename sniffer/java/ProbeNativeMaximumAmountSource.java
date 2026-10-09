import java.lang.reflect.*;
import java.util.*;
/** eWN.C/n/c amount source distinctions; original bytecode, no catalogs. */
public class ProbeNativeMaximumAmountSource {
 static void set(Object o,Class<?> owner,String name,Object v)throws Exception{Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(o,v);}
 static int apply(int amount,Integer trigger,Integer forced)throws Exception{
  fff stat=new fff(ffw.sgC,0,1000);stat.or(100);stat.on(40);
  Map<PC,fff> values=new HashMap<>();values.put(ffw.sgC,stat);
  eWN runner=new eWN(ffw.sgC);set(runner,Qe.class,"bfs",ProbeCombatArithmetic.actor(values,1));set(runner,Qe.class,"aSg",amount);
  if(forced!=null){eVt ctx=new eVt();ctx.SQ(forced);set(runner,Qe.class,"bfu",ctx);runner.n(null);}
  eXE source=null;if(trigger!=null){source=new eXE();set(source,Qe.class,"aSg",trigger);}
  Method c=eWN.class.getDeclaredMethod("c",Qe.class,boolean.class);c.setAccessible(true);c.invoke(runner,source,true);
  return stat.aYU();
 }
 public static void main(String[] args)throws Exception{
  int[][] rows={{-1,99},{7,107},{0,100}};
  if(apply(-1,null,null)!=99)throw new AssertionError("literal -1 without source");
  if(apply(-1,7,null)!=107)throw new AssertionError("actual trigger substitution");
  if(apply(-1,null,7)!=107)throw new AssertionError("context value before application");
  if(apply(-1,9,0)!=100)throw new AssertionError("forced0 overrides before trigger -1 check");
  System.out.println("PASS eWN literal-1/noQe=>-1;actualQe7=>7;eVtforced7=>7;forced0+Qe9=>0");
 }
}
