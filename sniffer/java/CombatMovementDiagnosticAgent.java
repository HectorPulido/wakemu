import com.google.gson.Gson;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
public class CombatMovementDiagnosticAgent {
 static Object call(Object obj,String name,Object...args)throws Exception {
  Class<?> c=obj instanceof Class?(Class<?>)obj:obj.getClass();
  for(Class<?> t=c;t!=null;t=t.getSuperclass())for(Method m:t.getDeclaredMethods())if(m.getName().equals(name)&&m.getParameterCount()==args.length){m.setAccessible(true);try{return m.invoke(obj instanceof Class?null:obj,args);}catch(IllegalArgumentException e){}}
  throw new NoSuchMethodException(name);
 }
 static Object field(Object obj,String name)throws Exception {
  for(Class<?> t=obj instanceof Class?(Class<?>)obj:obj.getClass();t!=null;t=t.getSuperclass())try{Field f=t.getDeclaredField(name);f.setAccessible(true);return f.get(obj instanceof Class?null:obj);}catch(NoSuchFieldException e){}
  throw new NoSuchFieldException(name);
 }
 public static void agentmain(String path,Instrumentation instrumentation)throws Exception {
  Map<String,Object> out=new LinkedHashMap<>();out.put("time",java.time.Instant.now().toString());
  try {
   Object dbe=call(Class.forName("dbe"),"fcF"),dba=call(Class.forName("dba"),"fcm");
   for(String key:new String[]{"NO","cEV","okd","oke","okf"})out.put("dbe."+key,field(dbe,key));
   for(String key:new String[]{"fcs","fct","fcA"})out.put("dba."+key,call(dba,key));
   Object target=call(dba,"fcn");out.put("target",String.valueOf(target));
   Object route=field(dbe,"okg");out.put("route",String.valueOf(route));if(route!=null)out.put("path_points",call(route,"bDT"));
   Object fight=call(dba,"cXY"),timeline=call(fight,"dLW"),actor=call(timeline,"dNG");
   out.put("actor_id",call(actor,"Xi"));out.put("actor_owned",call(actor,"doz"));out.put("actor_position",String.valueOf(call(actor,"baM")));
   out.put("actor_mp",call(actor,"c",field(Class.forName("ffw"),"sgE")));
  }catch(Throwable t){out.put("error",t.toString());}
  Files.writeString(Path.of(path),new Gson().toJson(out));
 }
}
