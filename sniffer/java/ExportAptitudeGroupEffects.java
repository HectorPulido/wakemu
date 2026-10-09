import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Export native child contracts for aptitude groups without flattening semantics. */
public class ExportAptitudeGroupEffects {
    static Map<Integer,int[]> groups = new HashMap<>();
    static Map<String,Object> effect(int id) {
        eVn e = bcA.dcX().AH(id);
        Object runner = eVi.fLJ().pS(e.awM());
        PC stat = runner instanceof eWN n ? n.fNI() : runner instanceof eWW n ? n.fNI() : null;
        Map<String,Object> row = new LinkedHashMap<>();
        row.put("effect", id); row.put("generic", e.awM()); row.put("runner", runner.getClass().getName());
        row.put("stat_id", stat == null ? -1 : stat.aKg() & 255);
        row.put("params", e.fKI()); row.put("criteria", e.fKT() != null);
        row.put("triggers", e.fKV().hasNext() || e.fKW().hasNext()); row.put("target_mask", e.aZR());
        List<Object> levels = new ArrayList<>();
        for (short level=1;level<=62;level++) {
            List<Integer> values = new ArrayList<>();
            for (int index=0;index<e.fKI().length/2;index++) values.add(e.a(index,level,eVh.rpA));
            levels.add(values);
        }
        row.put("values_by_points",levels);
        return row;
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>() {public void load(aKX row) {groups.put(row.d(),row.cku());}});
        List<Object> rows = new ArrayList<>();
        apw.bGL().a(new aJX(), new apB<aJX>() {public void load(aJX row) {
            if(row.cku().length==0)return;
            int id=row.cku()[0]; eVn e=bcA.dcX().AH(id);
            if(e.awM()!=330)return;
            Map<String,Object> result=effect(id); result.put("bonus",row.tJ());
            List<Object> children=new ArrayList<>();
            for(int child:groups.getOrDefault(id,new int[0]))children.add(effect(child));
            result.put("children",children); rows.add(result);
        }});
        Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(rows));
    }
}
