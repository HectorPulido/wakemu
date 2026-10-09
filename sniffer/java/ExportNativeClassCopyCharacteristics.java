import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Original aZU/aKz breed level curves used by eHI's source-character copy. */
public final class ExportNativeClassCopyCharacteristics {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        Map<String,Object> breeds=new TreeMap<>();
        apw.bGL().a(new aKz(),new apB<aKz>(){public void load(aKz record){
            eGE breed=eGE.PW(record.aXA());
            if(breed==null||record.aXA()<=0)return;
            Map<String,Object> curves=new TreeMap<>();
            for(var row:record.cmj().entrySet())
                curves.put(Integer.toString(row.getKey()&255),row.getValue());
            breeds.put(Integer.toString(record.aXA()),curves);
        }});
        Map<String,Object> fresh=new TreeMap<>();
        ffh pool=new ffh();
        for(ffw stat:ffw.values()){
            fff value=pool.e(stat);
            Map<String,Object> row=new LinkedHashMap<>();
            row.put("expandable",stat.isExpandable());
            row.put("over_max_current",stat.fZB());
            row.put("reset_minimum",stat.aZq());
            row.put("reset_maximum",stat.aZr());
            row.put("current",value.aYT());
            row.put("minimum",value.fZn());
            row.put("maximum",value.fZm());
            try {
                var field=fff.class.getDeclaredField("sfV");field.setAccessible(true);
                row.put("percentage",field.getInt(value));
            } catch(ReflectiveOperationException error){throw new IllegalStateException(error);}
            row.put("hard_minimum",stat.aZo());
            row.put("hard_maximum",stat.aZp());
            fresh.put(Integer.toString(stat.aKg()&255),row);
        }
        Map<String,Object> output=new LinkedHashMap<>();
        output.put("schema",1);
        output.put("source","Installed aZU.a(aKz) -> eGE.d -> eGX/eGU; fresh ffh/fff operands");
        output.put("breeds",breeds);
        output.put("fresh_characteristics",fresh);
        tA wire=new tA();pool.a(wire);
        List<Integer> order=new ArrayList<>();
        for(tB row:wire.abi)order.add(row.Sj&255);
        output.put("native_characteristic_order",order);
        Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting()
            .create().toJson(output)+"\n");
        System.out.println("Exported "+breeds.size()+" class copy curves / "+fresh.size()+" fresh PA definitions");
        System.exit(0);
    }
}
