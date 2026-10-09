import java.lang.reflect.*;import java.nio.file.*;import java.util.*;import com.google.gson.GsonBuilder;
/** Original eXc C/application, PA mutability and exact HP/property/clock ordering. */
public class ProbeNativeKillContract {
 static void set(Object o,Class<?> type,String name,Object value)throws Exception {Field f=type.getDeclaredField(name);f.setAccessible(true);f.set(o,value);}
 public static void main(String[]args)throws Exception {
  Method apply=eXc.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);
  List<Map<String,Object>>rows=new ArrayList<>();
  for(short level:new short[]{0,1,20,200,245,32767})for(int parameter:new int[]{-1,0,1,2})for(int count:new int[]{0,1})for(int hpMin:new int[]{0,5})for(boolean frozen:new boolean[]{false,true})for(boolean clockFrozen:new boolean[]{false,true}){
   eXc runner=new eXc();
   eVn effect=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->{
    if(m.getName().equals("fKJ"))return count;
    if(m.getName().equals("a")&&m.getReturnType()==int.class){if(((Short)a[1]).shortValue()!=level)throw new AssertionError("Wrong native C level");return parameter;}
    throw new UnsupportedOperationException(m.toString());});
   set(runner,Qe.class,"bfp",effect);set(runner,Qe.class,"bfq",null);
   eVt context=new eVt();context.SP(level);set(runner,Qe.class,"bfu",context);
   runner.C(null);
   fff hp=new fff(ffw.sgC,0,100);hp.or(100);hp.os(hpMin);hp.on(80);set(hp,fff.class,"sfT",frozen);
   fff clock=new fff(ffw.sgM,0,100);clock.or(10);clock.on(3);set(clock,fff.class,"sfT",clockFrozen);
   List<String>order=new ArrayList<>();hp.a(p->order.add("hp"));clock.a(p->order.add("clock"));
   PV actor=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},(p,m,a)->{
    if(m.getName().equals("a"))return a[0]==ffw.sgC||a[0]==ffw.sgM;
    if(m.getName().equals("b"))return a[0]==ffw.sgC?hp:clock;
    if(m.getName().equals("f")){if(a[0]!=ffe.seI)throw new AssertionError();order.add("property65");return null;}
    throw new UnsupportedOperationException(m.toString());});
   set(runner,Qe.class,"bfs",actor);apply.invoke(runner,null,false);
   boolean suppress=count>0&&parameter==1;
   if(hp.aYT()!=(frozen?80:hpMin)||clock.aYV()!=0||clock.aYS()!=0||order.contains("property65")!=suppress)throw new AssertionError("level="+level+" count="+count+" p="+parameter+" min="+hpMin+" frozen="+frozen+" hp="+hp.aYT()+" clockCurrent="+clock.aYT()+" raw="+clock.aYV()+" events="+order);
   Map<String,Object>r=new LinkedHashMap<>();r.put("level",level);r.put("parameter_count",count);r.put("parameter",parameter);r.put("hp_min",hpMin);r.put("hp_frozen",frozen);r.put("hp_after",hp.aYT());r.put("ko_raw_max",clock.aYV());r.put("ko_current",clock.aYS());r.put("ko_raw_current",clock.aYT());r.put("ko_frozen",clockFrozen);r.put("order",order);rows.add(r);
  }
  eXc prototype=new eXc();Map<String,Object>out=new LinkedHashMap<>();out.put("runner","eXc");out.put("events",prototype.bbw().stream().boxed().toList());out.put("bbz",prototype.bbz());out.put("bbA",prototype.bbA());out.put("bbB",prototype.bbB());out.put("hp_current_may_exceed_max",ffw.sgC.fZB());out.put("ko_current_may_exceed_max",ffw.sgM.fZB());out.put("hp_id",ffw.sgC.aKg()&255);out.put("ko_id",ffw.sgM.aKg()&255);out.put("property_id",ffe.seI.aKg()&255);out.put("rows",rows);
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(out));System.out.println("Native eXc rows="+rows.size()+" events="+out.get("events"));
 }
}
