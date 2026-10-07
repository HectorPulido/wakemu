import com.google.gson.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;

/** Parse all exported CraftTable instances using the installed native client classes. */
public final class ExportCraftTableCells {
  static Field field(Class<?> type, String name) throws Exception {
    for (Class<?> c=type; c!=null; c=c.getSuperclass()) {
      try { Field f=c.getDeclaredField(name); f.setAccessible(true); return f; }
      catch (NoSuchFieldException ignored) {}
    }
    throw new NoSuchFieldException(name);
  }
  public static void main(String[] args) throws Exception {
    JsonArray source=JsonParser.parseString(Files.readString(Path.of("server/protocol/native-map-objects.json"))).getAsJsonArray();
    Field bbz=field(bEG.class,"bbz");
    JsonArray out=new JsonArray(); int total=0;
    for(JsonElement e:source) {
      JsonObject in=e.getAsJsonObject(); if(!in.get("type").getAsString().equals("CraftTable")) continue;
      bEG obj=bEE.valueOf("CraftTable").bej().bau();
      obj.as(HexFormat.of().parseHex(in.get("payload_hex").getAsString()));
      int map=in.get("map_id").getAsInt(), x=obj.bcz(), y=obj.bcA(), z=obj.bcB();
      int mask=obj.bem(), facing=obj.bcy().dyI;
      JsonObject row=new JsonObject(); row.addProperty("map_id",map); row.addProperty("object_id",in.get("id").getAsLong());
      row.addProperty("definition_id",Integer.parseInt((String)bbz.get(obj)));
      row.addProperty("x",x); row.addProperty("y",y); row.addProperty("z",z);
      row.addProperty("interaction_mask",mask); row.addProperty("facing",obj.bcy().name()); row.addProperty("facing_angle",facing);
      row.addProperty("bEG_jRm",obj.dVL());
      JsonArray cells=new JsonArray();
      for(QV q:QV.aa((short)mask)) {
        JsonObject c=new JsonObject(); c.addProperty("direction",q.name()); c.addProperty("direction_bit",q.bef()); c.addProperty("rotation",q.beg());
        if(q==QV.valueOf("CENTER")) { c.addProperty("x",x); c.addProperty("y",y); }
        else { aAS d=aAS.wL((facing+q.beg())%8); c.addProperty("x",x+d.dyJ); c.addProperty("y",y+d.dyK); }
        c.addProperty("z",z); cells.add(c);
      }
      row.add("raw_interaction_candidates",cells); out.add(row); total++;
    }
    JsonObject result=new JsonObject(); result.addProperty("schema_version",1); result.addProperty("source","server/protocol/native-map-objects.json payload_hex parsed through client/lib/wakfu-client.jar bEE.CraftTable and bEG.dST QV/aAS math");
    result.addProperty("row_count",total); result.add("instances",out);
    System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(result));
  }
}
