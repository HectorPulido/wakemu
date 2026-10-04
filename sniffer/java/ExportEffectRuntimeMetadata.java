import java.nio.file.*;
import java.util.*;
import com.google.gson.Gson;
/** Offline compact metadata refresh, without recomputing level matrices. */
public class ExportEffectRuntimeMetadata {
    static Map<String,Object> definition(eVn effect) throws Exception {
        Map<String,Object> row=new LinkedHashMap<>();
        row.put("clock_on_caster",effect.aZT());row.put("clock_on_target",effect.aZU());
        String[] fields=effect.getClass()==eVy.class ? new String[]{"ryE","ryF","ryG","ryH","ryI","esr"} : effect.getClass()==eVH.class ? new String[]{"rzv","rzw"} : new String[]{};
        for(String name:fields) {var f=effect.getClass().getDeclaredField(name);f.setAccessible(true);row.put(name,f.get(effect));}
        return row;
    }
    static Object timer(Tt t) {
        return t==null ? null : List.of((int)t.biT(),t.biN(),(int)t.biQ(),t.biR());
    }
    static Map<String,Object> timing(eVn effect, short level) {
        Map<String,Object> row=new LinkedHashMap<>();
        if(effect instanceof eVv timed) {row.put("duration",timer(timed.en(level)));row.put("delay",timer(timed.eo(level)));row.put("cxq",timed.cxq());}
        if(effect instanceof eVG timed) row.put("realtime",timed.ep(level));
        return row;
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        Map<String,Object> rows = new LinkedHashMap<>();
        for (String line : Files.readAllLines(Path.of(args[0]))) {
            int reference = Integer.parseInt(line);
            eVn effect = bcA.dcX().AH(reference);
            if (effect == null) throw new IllegalStateException("Missing effect "+reference);
            List<Integer> flags = new ArrayList<>();
            for (eVl flag : eVl.values()) if (effect.a(flag)) flags.add((int)flag.fLK());
            Map<String,Object> clocks=new LinkedHashMap<>();
            for(short level:new short[]{0,1,200,32767}) clocks.put(Short.toString(level),timing(effect,level));
            rows.put(line, Map.of("native_definition_class",effect.getClass().getName(),
                                 "native_timing_checks",clocks,
                                 "native_timing_definition",definition(effect),"native_effect_flags",flags,
                                 "native_localization_enabled",effect.aZQ(),
                                 "native_execution_mode",(int)effect.aZD()));
        }
        Files.writeString(Path.of(args[1]), new Gson().toJson(rows));
        System.out.println("Exported runtime flags for "+rows.size()+" effects");
    }
}
