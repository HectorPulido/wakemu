import java.nio.file.*;import java.lang.reflect.*;import java.util.*;import com.google.gson.*;
/** Offline native binary export. Does not initialize network/client sessions. */
public class ExportMonsterEncyclopedia {
 static Object raw(Object o)throws Exception{
  if(o==null||o instanceof Number||o instanceof Boolean||o instanceof String)return o;
  if(o.getClass().isArray()){List<Object>a=new ArrayList<>();for(int i=0;i<Array.getLength(o);i++)a.add(raw(Array.get(o,i)));return a;}
  Map<String,Object>m=new TreeMap<>();m.put("native_class",o.getClass().getName());
  for(Method f:o.getClass().getDeclaredMethods())if(Modifier.isPublic(f.getModifiers())&&f.getParameterCount()==0&&!f.getName().equals("reset")&&!f.getName().equals("bGI")&&!f.getReturnType().equals(Void.TYPE))m.put(f.getName(),raw(f.invoke(o)));
  return m;
 }
 public static void main(String[]args)throws Exception{
  Path output=Path.of(args.length>0?args[0]:"server/protocol/monster-encyclopedia.json");
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Object>monsters=new ArrayList<>();
  apw.bGL().a(new aMb(),new apB<aMb>(){public void load(aMb r){try{
   Map<String,Object>m=new LinkedHashMap<>();m.put("ref",r.d());m.put("family_id",r.cqM());m.put("raw_native",raw(r));
   List<Object>drops=new ArrayList<>();for(aMf d:r.csr()){
    Map<String,Object>x=new LinkedHashMap<>();x.put("reference_id",d.aAi());x.put("probability",d.cmY());x.put("roll_count",d.csD());x.put("quantity_min",d.cqy());x.put("quantity_max",d.cqz());x.put("is_loot_table",d.cqA());x.put("complex_criteria",d.csH());x.put("native_csE",d.csE());x.put("native_csF",d.csF());
    List<Object>conditions=new ArrayList<>();int[]c=d.csG();if(c.length%2!=0)throw new IllegalStateException("Odd native criteria array");
    for(int i=0;i<c.length;i+=2){blo condition=blo.DU(c[i]);Map<String,Object>v=new LinkedHashMap<>();v.put("id",c[i]);v.put("value",c[i+1]);v.put("native_enum",condition==null?null:condition.name());conditions.add(v);}x.put("conditions",conditions);drops.add(x);
   }m.put("combat_drops",drops);m.put("collect_actions",raw(r.csk()));
   List<Object>collectItems=new ArrayList<>();for(aMi action:r.csk()){Map<String,Object>x=new LinkedHashMap<>();x.put("action_id",action.d());x.put("item_ref",action.csP());x.put("condition_expression",action.clT());x.put("duration_ms",action.getDuration());x.put("raw_native",raw(action));collectItems.add(x);}m.put("collect_items",collectItems);m.put("world_actions",raw(r.csj()));m.put("raw_csl",raw(r.csl()));m.put("raw_csm",raw(r.csm()));monsters.add(m);
  }catch(Exception e){throw new RuntimeException(e);}}});
  monsters.sort(Comparator.comparingInt(o->((Number)((Map<?,?>)o).get("ref")).intValue()));
  Map<String,Object>result=new LinkedHashMap<>();result.put("schema_version",1);result.put("source","Installed aMb/aMf binary tables loaded offline through apw; no network");result.put("count",monsters.size());result.put("monsters",monsters);
  List<Object>lootTables=new ArrayList<>();
  apw.bGL().a(new fFc(),new apB<fFc>(){public void load(fFc r){try{lootTables.add(raw(r));}catch(Exception e){throw new RuntimeException(e);}}});
  result.put("external_loot_tables",lootTables);
  List<Object>territories=new ArrayList<>();
  apw.bGL().a(new aMD(),new apB<aMD>(){public void load(aMD r){try{Map<String,Object>m=new LinkedHashMap<>();m.put("territory_id",r.ctH());m.put("family_entries",raw(r.ctN()));m.put("raw_native",raw(r));territories.add(m);}catch(Exception e){throw new RuntimeException(e);}}});
  result.put("territories",territories);
  result.put("base_combat_xp",null);
  Files.writeString(output,new GsonBuilder().setPrettyPrinting().serializeNulls().create().toJson(result));System.out.println(monsters.size());
 }
}
