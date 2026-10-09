import java.nio.file.*;import java.util.*;import com.google.gson.*;
/** Exact class-closure fyW.elk, including original enum identity and ordinal. */
public class ExportNativeClassStateResistance {
 public static void main(String[] args)throws Exception{
  JsonObject seeds=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  fyZ.guX().a(new bbV());
  Map<String,Object> rows=new TreeMap<>();List<Integer> missing=new ArrayList<>();int checks=0;
  for(JsonElement entry:seeds.getAsJsonArray("state_ids")){
   int id=entry.getAsInt();fyW state=fyZ.guX().aax(id);
   if(state==null){missing.add(id);continue;}
   if(state.guI()!=id)throw new AssertionError("Native state identity mismatch");
   fza mode=state.elk();if(mode==null)throw new AssertionError("Native resistance mode null");
   for(short level:new short[]{0,1,20,200,245,32767}){
    fyW selected=state.cu(level);
    if(selected.guI()!=id || selected.elk()!=mode)throw new AssertionError("Level-dependent state resistance mode");checks++;
   }
   rows.put(Integer.toString(id),Map.of("native_resistance_mode",Map.of(
     "enum_class","fza","name",mode.name(),"ordinal",mode.ordinal()),"native_getter","fyW.elk"));
  }
  Map<String,Object> enums=new LinkedHashMap<>();for(fza mode:fza.values())enums.put(mode.name(),mode.ordinal());
  Map<String,Object> out=new LinkedHashMap<>();out.put("schema","native-class-state-resistance-v1");
  out.put("seed_identity",seeds);out.put("enum_ordinals",enums);out.put("states",rows);
  out.put("missing_state_ids",missing);out.put("native_level_checks",checks);
  Files.writeString(Path.of(args[1]),new GsonBuilder().serializeNulls().create().toJson(out)+"\n");
  System.out.println("Original class state resistance: "+rows.size()+" states, "+checks+" checks, missing="+missing);
 }
}
