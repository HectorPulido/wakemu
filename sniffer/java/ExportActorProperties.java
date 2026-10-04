import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import com.google.gson.Gson;
/** Offline native breed properties as consumed by eGj.d(eGH). */
public class ExportActorProperties {
 static Object canonical(Object value){
  if(value instanceof Map<?,?> m){Map<String,Object> sorted=new TreeMap<>();m.forEach((k,v)->sorted.put(k.toString(),canonical(v)));return sorted;}
  return value;
 }
 public static void main(String[] args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Method convert=bbo.class.getDeclaredMethod("a",aMb.class,short.class);convert.setAccessible(true);
  Map<String,Object> npc=new TreeMap<>();
  apw.bGL().a(new aMb(),new apB<aMb>(){public void load(aMb r){try{
   blj breed=(blj)convert.invoke(null,r,(short)r.d());
   npc.put(""+r.d(),Map.of("fight_properties",breed.fsp(),"world_properties",breed.fsq()));
  }catch(Exception e){throw new RuntimeException(e);}}});
  Map<String,Object> properties=new TreeMap<>();
  for(ffe p:ffe.values())properties.put(""+(p.aKg()&255),p.toString());
  Map<String,Object> result=Map.of("source","eGj.d(eGH) loads fsp with ffe.Ua; bbo.a(aMb,short)->blj; eGE.pIq.fsp empty",
   "player",Map.of("fight_properties",eGE.pIq.fsp(),"world_properties",eGE.pIq.fsq()),"npc",npc,"properties",properties);
  Files.writeString(Path.of(args.length==0?"server/protocol/native-actor-properties.json":args[0]),new Gson().toJson(canonical(result)));
  System.out.println("Exported "+npc.size()+" native NPC property profiles");
 }
}
