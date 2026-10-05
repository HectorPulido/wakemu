import java.lang.reflect.*;
import java.util.*;
/** Original eYE.a(PJ), used by both light damage fau and healing fat. */
public class ProbeNativeHighestElement {
 static PV actor(Map<Integer,Integer> stats){return (PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
  if(a!=null&&a.length==1&&a[0] instanceof PC){int key=((PC)a[0]).aKg()&255;
   if(m.getName().equals("a"))return stats.containsKey(key);
   if(m.getName().equals("c"))return stats.getOrDefault(key,0);
   if(m.getName().equals("b")){fff stat=new fff((ffw)a[0],-50000,50000);stat.or(50000);stat.on(stats.getOrDefault(key,0));Field raw=fff.class.getDeclaredField("bqD");raw.setAccessible(true);raw.setInt(stat,stats.getOrDefault(key,0));return stat;}}
  Class<?> type=m.getReturnType();if(type==boolean.class)return false;
  if(type==int.class)return 0;if(type==short.class)return (short)0;
  if(type==byte.class)return (byte)0;if(type==long.class)return 0L;
  if(type==float.class)return 0f;if(type==double.class)return 0d;return null;});}
 public static void main(String[]args){
  for(eVg e:eVg.values())System.out.println(e.name()+" id="+e.aKg()+" mastery="+(e.fLC()==null?null:e.fLC().aKg()&255));
  Map<Integer,Integer> stats=new HashMap<>();
  if(eYE.a(actor(stats))!=null)throw new AssertionError("absence must remain null");
  for(eVg e:eVg.values())if(e.fLC()!=null&&e!=eVg.rpj&&e!=eVg.rpk)stats.put(e.fLC().aKg()&255,-100);
  eVg first=eYE.a(actor(stats));
  if(first==null)throw new AssertionError("negative values must still select");
  eVg expected=null;for(eVg e:eVg.values())if(e.fLC()!=null&&e!=eVg.rpj&&e!=eVg.rpk){expected=e;break;}
  if(first!=expected)throw new AssertionError("equal values preserve enum order");
  stats.put(eVg.rpi.fLC().aKg()&255,300);
  if(eYE.a(actor(stats))!=eVg.rpi)throw new AssertionError("highest elemental mastery");
  for(Map<Integer,Integer> values:List.of(Map.<Integer,Integer>of(),Map.of(21,100,22,300),Map.of(21,-100))){
   fat heal=new fat(actor(values),actor(Map.of()),eVg.rpk,eVI.fMg());
   heal.Tf(1);heal.setValue(10);heal.fSy();
   int best=values.isEmpty()?0:Collections.max(values.values());
   int expectedValue=Math.max(1,10+best/10);
   if(heal.getValue()!=expectedValue)throw new AssertionError("light heal="+heal.getValue()+" expected="+expectedValue);
  }
  System.out.println("PASS native light fat arithmetic empty, positive and negative mastery");
  System.out.println("PASS highest selector: absent null, negative/equal enum order, strictly higher replacement");
 }
}
