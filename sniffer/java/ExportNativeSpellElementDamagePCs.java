import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Actual eYW.fQG element PC authority; no content loading or network. */
public final class ExportNativeSpellElementDamagePCs {
    public static void main(String[] args) throws Exception {
        Map<String,Object> elements = new TreeMap<>();
        for(int raw=-128; raw<=127; raw++) {
            eVg element=eVg.fa((byte)raw);
            if(element==null) continue;
            Map<String,Object> row=new LinkedHashMap<>();
            row.put("native_element", raw);
            row.put("element_name", element.name());
            row.put("damage_stat", element.fLC()==null?null:element.fLC().aKg());
            elements.put(Integer.toString(raw), row);
        }
        Files.writeString(Path.of(args[0]), new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(
            Map.of("source", "eYW.fQG.fyG.gtZ.fyF.gtQ.eVg.fa.fLC.aKg.v1", "null_pc_present", new ffh().g(null), "elements", elements))+"\n");
    }
}
