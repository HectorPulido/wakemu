import java.util.*;
/** Original fau LIGHT vs matching normal element, including coefficient masking. */
public class ProbeNativeLightDamage {
 static PV actor(Map<PC,Integer> stats,int x){
  PV delegate=ProbeDirectionalDamage.actor(stats,x,1);
  return (PV)java.lang.reflect.Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},(p,m,a)->{
   if(m.getName().equals("b")){fff stat=new fff((ffw)a[0],-1000000,1000000);stat.or(1000000);stat.on(stats.getOrDefault(a[0],0));return stat;}
   try{return m.invoke(delegate,a);}catch(java.lang.reflect.InvocationTargetException e){throw e.getCause();}
  });
 }
 public static void main(String[] args) {
  Map<PC,Integer> source=Map.of(ffw.sgR,100,ffw.sgS,200,ffw.sgT,0,ffw.sgU,0);
  Map<PC,Integer> target=Map.of(ffw.sgW,0,ffw.sgX,100,ffw.sgY,0,ffw.sgZ,0);
  if(eYE.a(actor(source,1))!=eVg.rpg)throw new AssertionError("water selection");
  if(eYE.a(ProbeDirectionalDamage.actor(Map.of(ffw.sgR,-10,ffw.sgS,-10),1,1))!=eVg.rpf)throw new AssertionError("negative tie");
  for(int mask=0;mask<4;mask++) {
   int[] values=new int[2];int i=0;
   for(eVg element:new eVg[]{eVg.rpk,eVg.rpg}){
    fau f=new fau(actor(source,1),actor(target,0),element,null);
    f.setValue(100);f.Tf(mask);f.mq(false);f.mw(true);f.fSy();values[i++]=f.getValue();
   }
   if(values[0]!=values[1])throw new AssertionError(Arrays.toString(values));
   System.out.println("mask="+mask+" LIGHT="+values[0]);
  }
  if(!ProbeNativeDamageEventIds.events(1083,11).get(11))throw new AssertionError("LIGHT event11");
 }
}
