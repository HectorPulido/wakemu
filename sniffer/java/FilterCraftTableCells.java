import com.google.gson.*;
import java.nio.file.*;
import java.util.*;

/** Apply native VF.v topology surface validation to the raw bEG.dST candidates. */
public final class FilterCraftTableCells {
  public static void main(String[] args) throws Exception {
    Path source=Path.of(args.length>0?args[0]:".runtime/local/craft-table-interaction-export/craft-table-interaction-candidates.json");
    JsonObject result=JsonParser.parseString(Files.readString(source)).getAsJsonObject();
    String template="jar:file:"+Path.of("client/contents/maps/tplg").toAbsolutePath()+"/%d.jar!/";
    VF.dd(template); VF.bms();
    // Match the installed geometry exporter’s native movement profile Sm(3,0,2,true).
    VF.a((short)3,(byte)0,(short)2);
    int currentMap=-1,total=0,accepted=0,errors=0; JsonArray instances=result.getAsJsonArray("instances");
    for(JsonElement element:instances) {
      JsonObject row=element.getAsJsonObject(); int map=row.get("map_id").getAsInt();
      if(map!=currentMap) { VF.reset(); VF.fs(map); currentMap=map; }
      JsonArray filtered=new JsonArray();
      for(JsonElement raw:row.getAsJsonArray("raw_interaction_candidates")) {
        JsonObject candidate=raw.getAsJsonObject(); int x=candidate.get("x").getAsInt(),y=candidate.get("y").getAsInt(),z=candidate.get("z").getAsInt(); total++;
        try {
          VF.g((short)Ve.qb(x),(short)Ve.qc(y)); short resolved=VF.v(x,y,(short)z);
          if(resolved!=-32768) { JsonObject cell=candidate.deepCopy(); cell.addProperty("z",(int)resolved); filtered.add(cell); accepted++; }
        } catch(Throwable failure) {
          if(failure instanceof VirtualMachineError) throw failure;
          errors++;
        }
      }
      row.add("vf_walkable_interaction_cells",filtered);
    }
    result.addProperty("native_filter","Installed VF.g + VF.v after the raw bEG.dST QV/orientation transform; rejected when VF.v returns -32768");
    result.addProperty("native_filter_profile","Sm(3,0,2,true), same explicit movement profile used by sniffer/java/ExportAllCombatMaps.java for static walk topology; not asserted as the live character-specific profile");
    result.addProperty("candidate_count",total); result.addProperty("vf_walkable_candidate_count",accepted); result.addProperty("vf_filter_errors",errors);
    System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(result));
  }
}
