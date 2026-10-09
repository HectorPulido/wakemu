import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Class-scoped fyF metadata used by original faC/faE/eZx copy-book builders. */
public final class ExportNativeCopiedClassSpellFlags {
    public static void main(String[] args) throws Exception {
        JsonObject scope=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        Set<Integer> references=new TreeSet<>();
        for(JsonElement row:scope.getAsJsonArray("class_spells"))
            references.add(row.getAsJsonObject().get("id").getAsInt());
        for(JsonElement reference:scope.getAsJsonArray("granted_spell_references"))
            references.add(reference.getAsInt());
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX row){}});
        apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw row){}});
        Map<String,Object> spells=new TreeMap<>();
        apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr record){
            if(!references.contains(record.d()))return;
            bPK spell=bPS.elL().IP(record.d());
            eVg element=eVg.fa(spell.gtQ());
            Map<String,Object> row=new LinkedHashMap<>();
            row.put("native_elO",spell.elO());
            row.put("native_element",spell.gtQ());
            row.put("element_name",element==null?null:element.name());
            row.put("native_elemental_copy",element==null?null:element.fLF());
            row.put("native_neutral_copy",element==eVg.rpl);
            spells.put(Integer.toString(record.d()),row);
        }});
        Set<Integer> missing=new TreeSet<>(references);
        for(String reference:spells.keySet())missing.remove(Integer.parseInt(reference));
        Map<String,Object> output=new LinkedHashMap<>();
        output.put("schema",1);
        output.put("source","Installed fyF.elO/gtQ and eVg.fa/fLF/rpl; faC/faE class-book scope only");
        output.put("copy_level_minimum",MX.aYm.aWb());
        output.put("copy_level_maximum",MX.aYm.aWa());
        output.put("scope",references);
        output.put("missing",missing);
        output.put("spells",spells);
        Files.writeString(Path.of(args[1]),new GsonBuilder().serializeNulls().setPrettyPrinting()
            .create().toJson(output)+"\n");
        System.out.println("Exported "+spells.size()+" class copy-book metadata rows; missing="+missing.size());
        System.exit(0);
    }
}
