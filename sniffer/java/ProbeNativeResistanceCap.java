import java.lang.reflect.*;
/** Original eWR.C and fNM with actual PA and ordered Qf; no game/network. */
public class ProbeNativeResistanceCap {
 static class Manager extends Qf {public Qi bci(){return null;}void put(long id,Qe e){bfT.put(id,e);}void erase(long id){bfT.remove(id);}}
 static void set(Object object,String name,Object value)throws Exception{
  Class<?> c=object.getClass();while(c!=null){try{Field f=c.getDeclaredField(name);f.setAccessible(true);f.set(object,value);return;}catch(NoSuchFieldException ex){c=c.getSuperclass();}}
  throw new NoSuchFieldException(name);
 }
 static eWR runner(PV target,int amount)throws Exception{
  eWR e=new eWR(ffw.fK((byte)27),fap.rJR);e.lV(90);e.fc((byte)0);
  set(e,"bfs",target);set(e,"aSg",amount);set(e,"rCB",amount);return e;
 }
 public static void main(String[]args)throws Exception{
  Manager manager=new Manager();fff stat=new fff(ffw.fK((byte)27),-1000,1000);stat.or(1000);stat.os(-1000);stat.on(0);
  PV target=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->{
   if(m.getName().equals("bax"))return manager;if(m.getName().equals("b")&&a!=null&&a.length==1)return stat;
   if(m.getName().equals("toString"))return "owned resistance target";throw new UnsupportedOperationException(m.getName());});
  eWR first=runner(target,150);first.C(null);first.d(stat);manager.put(1,first);
  eWR second=runner(target,100);second.C(null);
  if(second.getValue()!=50)throw new AssertionError("cap="+second.getValue());
  second.d(stat);manager.put(2,second);
  if(stat.aYT()!=-200)throw new AssertionError("applied="+stat.aYT());
  manager.erase(1);first.fNM();
  if(stat.aYT()!=-100||second.getValue()!=100)throw new AssertionError("redistribution="+stat.aYT()+"/"+second.getValue());
  manager.erase(2);second.fNM();if(stat.aYT()!=0)throw new AssertionError("final="+stat.aYT());
  first=runner(target,150);first.C(null);first.d(stat);manager.put(1,first);
  second=runner(target,100);eVt transfer=new eVt();transfer.SQ(100);
  set(second,"bfu",transfer);second.n(null);second.d(stat);
  if(second.getValue()!=100||stat.aYT()!=-250||second.Mt()!=100)
   throw new AssertionError("cap must precede forced value, requested must remain100");
  System.out.println("PASS original cap200, ordered refill, final removal and postcap transfer");
 }
}
