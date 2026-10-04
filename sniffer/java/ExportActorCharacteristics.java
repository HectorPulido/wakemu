import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.zip.GZIPOutputStream;
import com.google.gson.Gson;
/** Native fresh ffh and lazy NPC ffx/ffC definitions, without network. */
public class ExportActorCharacteristics {
    static Map<String,Object> value(fff v)throws Exception{
        Field frozen=fff.class.getDeclaredField("sfT");frozen.setAccessible(true);
        return Map.of("current",v.aYS(),"minimum",v.aYW(),"maximum",v.aYU(),"frozen",frozen.getBoolean(v));
    }
    public static void main(String[] args)throws Exception{
        Path output=Path.of(args.length==0?"server/protocol/native-actor-characteristics.json.gz":args[0]);
        Map<String,Object> definitions=new TreeMap<>();ffh fresh=new ffh();
        for(ffw s:ffw.values()){
            Map<String,Object> row=new LinkedHashMap<>(value(fresh.e(s)));
            row.put("name",s.toString());row.put("hard_minimum",s.aZo());row.put("hard_maximum",s.aZp());
            row.put("native_default",s.aZs());row.put("expandable",s.isExpandable());
            definitions.put(""+(s.aKg()&255),row);
        }
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        Method convert=bbo.class.getDeclaredMethod("b",aMb.class);convert.setAccessible(true);
        Map<String,Object> monsters=new TreeMap<>();
        apw.bGL().a(new aMb(),new apB<aMb>(){public void load(aMb r){try{
            @SuppressWarnings("unchecked") EnumMap<ffw,ayH<Integer,Float>> curves=(EnumMap<ffw,ayH<Integer,Float>>)convert.invoke(null,r);
            ffC base=new ffC(r.cqN());Map<String,Object> stats=new TreeMap<>();
            for(var entry:curves.entrySet()){
                var pair=entry.getValue();base.a(entry.getKey(),pair.getFirst(),pair.aIy());
                stats.put(""+(entry.getKey().aKg()&255),List.of(pair.getFirst(),pair.aIy()));
            }
            ffx atMinimum=new ffx(base,r.cqN());Map<String,Object> check=new TreeMap<>();
            for(ffw s:ffw.values())check.put(""+(s.aKg()&255),value(atMinimum.e(s)));
            Map<String,Object> maximumCheck=new TreeMap<>();
            ffx atMaximum=new ffx(base,r.cqO());
            for(ffw s:ffw.values())maximumCheck.put(""+(s.aKg()&255),value(atMaximum.e(s)));
            monsters.put(""+r.d(),Map.of("base_level",r.cqN(),"maximum_level",r.cqO(),
                "physical_radius",(int)(byte)r.csa(),"curves",stats,"at_base_level",check,"at_maximum_level",maximumCheck));
        }catch(Exception e){throw new RuntimeException(e);}}});
        Map<String,Object> result=Map.of("source","Native ffh/fff; bbo.b(aMb), ffC and ffx; radius aMb.csa->blj->eGC.bcL",
            "characteristics",definitions,"npc_profiles",monsters,"default_actor_radius",(int)eGE.pIq.bcL());
        try(var stream=new GZIPOutputStream(Files.newOutputStream(output))){stream.write(new Gson().toJson(result).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
        System.out.println("Exported "+definitions.size()+" characteristics and "+monsters.size()+" NPC profiles to "+output);
    }
}
