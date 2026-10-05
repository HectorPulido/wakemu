import java.lang.reflect.*;
import java.util.*;

/** Installed eWu mutation/C and fyW packing, without loading game assets. */
public final class ProbeNativeStateTriggerValue430 {
 static final class Runner extends eWu {
  Runner(int level) { kFB=3442; rBo=(short)level; rBp=rBo; rBn=fyW.ae(kFB,rBo); aSg=77; }
  void definition(eVn value) { bfp=value; }
  void environment(PN value) { bfw=value; }
  int level(){return rBo;} int seed(){return rBp;} int packed(){return rBn;}
 }
 static Object primitive(Class<?> type) {
  if(type==boolean.class)return false;if(type==int.class)return 0;
  if(type==short.class)return (short)0;if(type==byte.class)return (byte)0;
  if(type==long.class)return 0L;if(type==float.class)return 0f;
  if(type==double.class)return 0d;return null;
 }
 static eVn definition() {return (eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->{
  if(m.getName().equals("a") && a!=null && a.length==3 && a[0] instanceof Integer)return ((Integer)a[0])==0?3442:9;
  return primitive(m.getReturnType());
 });}
 static int checks=0;
 static void exact(int start,int mode,float amount,boolean replace,int expected){
  Runner r=new Runner(start);r.a(mode,amount,replace);
  if(r.level()!=expected || r.seed()!=expected || fyW.aar(r.packed())!=3442 || fyW.aaf(r.packed())!=expected || r.getValue()!=77)
   throw new AssertionError("mode="+mode+" start="+start+" got="+r.level());
  checks++;
 }
 public static void main(String[]args)throws Exception{
  exact(10,4,2.9f,false,12);exact(10,4,-2.9f,false,7);exact(10,4,2.9f,true,2);
  exact(32767,4,1,false,-32768);exact(-32768,4,-1,false,32767);
  exact(10,4,Float.NaN,true,0);exact(10,4,Float.POSITIVE_INFINITY,true,-1);
  exact(10,7,50,false,15);exact(10,7,50,true,5);exact(-10,7,50,true,-5);
  exact(32767,7,100,false,-2);exact(10,0,50,true,10);exact(10,1,2,false,10);
  for(int i=0;i<30;i++){
   Runner r=new Runner(3);r.a(7,50,true);
   if(r.level()!=1 && r.level()!=2)throw new AssertionError("Native stochastic bound");
   checks++;
  }
  Runner r=new Runner(20);r.definition(definition());r.a(4,3,false);r.C(null);
  if(r.level()!=9 || r.seed()!=9 || fyW.aaf(r.packed())!=9)throw new AssertionError("C reseeds pre-C mutation");checks++;
  eVt context=eVt.a(true,false,null);
  context.a(new eVz(){public void h(eZR value){} public void i(eZR value){
   if(r.level()!=9)throw new AssertionError("callback must follow C");value.a(4,3,false);
  }});
  r.a(context);r.n(null);
  if(r.level()!=12 || r.seed()!=12 || fyW.aaf(r.packed())!=12 || r.getValue()!=77)throw new AssertionError("callback after C updates short fields only");checks++;
  fyW raw=new fyW();for(String name:new String[]{"tyt","tys"}){
   Field f=fyW.class.getDeclaredField(name);f.setAccessible(true);f.setShort(raw,(short)(name.equals("tyt")?3442:400));
  }
  fyW capped=raw.cu((short)500);Field packed=fyW.class.getDeclaredField("dIy");packed.setAccessible(true);
  if(capped.cmZ()!=400 || fyW.aaf(packed.getInt(capped))!=500)throw new AssertionError("effective level and raw packed differ");checks++;
  if(raw.cu((short)-1).cmZ()!=-1)throw new AssertionError("No lower clamp in fyW.cu");checks++;
  List<String> notices=new ArrayList<>();
  PR observer=(PR)Proxy.newProxyInstance(PR.class.getClassLoader(),new Class[]{PR.class},(p,m,a)->{notices.add(m.getName());return primitive(m.getReturnType());});
  PN environment=(PN)Proxy.newProxyInstance(PN.class.getClassLoader(),new Class[]{PN.class},(p,m,a)->m.getName().equals("baa")?observer:primitive(m.getReturnType()));
  Runner normal=new Runner(10);normal.definition(definition());normal.environment(environment);normal.d(null,false);normal.d(null,false);
  if(!notices.equals(List.of("b")))throw new AssertionError("Single notice");checks++;
  notices.clear();Runner suppressed=new Runner(10);suppressed.definition(definition());suppressed.environment(environment);suppressed.fRS();suppressed.d(null,false);
  if(!notices.isEmpty() || suppressed.level()!=10 || suppressed.getValue()!=77)throw new AssertionError("fRS notification suppression only");checks++;
  System.out.println("PASS "+checks+" installed eWu/fyW/notification checks; no game catalog loaded");
 }
}
