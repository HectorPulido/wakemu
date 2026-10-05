import java.nio.file.*;import java.util.*;import com.google.gson.Gson;
public class ExportNativeWorldProperties {
 public static void main(String[]args)throws Exception{Map<String,Object>rows=new TreeMap<>();for(eHQ p:eHQ.values())rows.put(Integer.toString(p.aKg()),Map.of("name",p.name(),"fight_property",p.fxg()==null?-1:p.fxg().aKg()));Files.writeString(Path.of(args[0]),new Gson().toJson(Map.of("source","Original eHQ enum IDs, names and fxg fight fallback, eMW HasWorldProperty", "properties",rows))+"\n");for(int id:new int[]{43,49,99}){eHQ p=eHQ.Qm(id);System.out.println(id+" "+p.name()+" fightFallback="+(p.fxg()==null?-1:p.fxg().aKg()));}}
}
