import java.lang.reflect.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Reproducible offline eVi registry metadata for exact eWQ/eWR and null400. */
public class ExportEffectRegistry {
    static Object canonical(Object value) {
        if(value instanceof Map<?,?> source) {
            Map<String,Object> result=new TreeMap<>();
            source.forEach((key,item)->result.put(key.toString(),canonical(item)));return result;
        }
        if(value instanceof List<?> source)return source.stream().map(ExportEffectRegistry::canonical).toList();
        return value;
    }
    static Object field(Object object,Class<?> owner,String name)throws Exception {
        Field field=owner.getDeclaredField(name);field.setAccessible(true);return field.get(object);
    }
    static Map<String,Object> guard(String method,String predicate,Map<String,Object> values) {
        Map<String,Object> result=new LinkedHashMap<>();result.put("native_method",method);
        result.put("predicate",predicate);result.putAll(values);return result;
    }
    static Map<String,Object> row(eVj entry)throws Exception {
        Object runner=entry.bkv();String name=runner.getClass().getSimpleName();
        Map<String,Object> row=new LinkedHashMap<>();row.put("effect_class",entry.d());row.put("runner",name);
        if(runner.getClass()==eWQ.class || runner.getClass()==eWR.class) {
            eWW effect=(eWW)runner;PC stat=effect.fNI();
            row.put("operation",name.equals("eWQ")?"gain_current":"lose_current");
            row.put("fixed_stat_id",stat==null?null:stat.aKg()&255);
            row.put("fixed_stat_name",stat==null?null:stat.toString());
            row.put("dynamic_stat",stat==null);
            row.put("percent_default",field(effect,eWW.class,"rCC"));
            Method zeroGuard=eWW.class.getDeclaredMethod("fMz");zeroGuard.setAccessible(true);
            row.put("zero_initial_amount_rejected",zeroGuard.invoke(effect));
            fap limit=runner instanceof eWR?(fap)field(effect,eWR.class,"rCx"):null;
            row.put("native_limit_policy",limit==null?null:limit.name());
            row.put("limit_policy",limit==null?"NORMAL":limit.name());
            row.put("parameter_contract",Map.of("supported_counts",List.of(1,2,3),"amount_index",0,
                "percent_index",1,"percent_true_value",1,"dynamic_stat_index",2,"trigger_copy_value",-1,
                "unsupported_counts",List.of(4,5)));
            row.put("additional_fields",Map.of("stat_id",12,"requested",25));
            List<Object> guards=new ArrayList<>();
            guards.add(guard("eWW.fMy","target_has_selected_characteristic",Map.of()));
            if(runner instanceof eWQ)guards.add(guard("eWQ.fMy","companion_prospection_requires_flag",
                Map.of("stat_id",ffw.shb.aKg()&255,"actor_kind",5,"bypass_flag",(int)eVl.rwR.fLK(),
                    "bypass_flag_name",eVl.rwR.name())));
            else guards.add(guard("eWR.fMy","target_property_blocks_stat",
                Map.of("stat_id",ffw.sgE.aKg()&255,"property_id",ffe.sdB.aKg()&255,"property_name",ffe.sdB.name())));
            row.put("source_guards",guards);
            row.put("limit_policy_requires_owned_stack",limit==fap.rJR);
        } else if(runner.getClass()==eYO.class) {
            PC stat=((eYO)runner).fNI();
            if(stat==null || stat.aZn()!=0)throw new IllegalStateException("Non-numeric forced characteristic");
            row.put("operation","set_current");row.put("fixed_stat_id",stat.aKg()&255);
            row.put("fixed_stat_name",stat.toString());row.put("dynamic_stat",false);
            row.put("parameter_contract",Map.of("supported_counts",List.of(0,1,2,3),"amount_index",0,"set_maximum_index",1,"percent_index",2));
            row.put("additional_fields",Map.of("set_maximum",17,"percent",18));
            row.put("removal_reverts",false);
        } else if(entry.d()==400 && runner.getClass()==eXE.class) {
            row.put("operation","none");row.put("fixed_stat_id",null);row.put("dynamic_stat",false);
            row.put("parameter_contract",Map.of("status_parameter_index",0,"evaluation_level",0,
                "signed_byte_cast",true,"parameterless_status",-1,
                "parameterless_status_policy","preserve_existing_status","current_stat_change",false));
            row.put("additional_fields",Map.of());row.put("source_guards",List.of());
        } else return null;
        return row;
    }
    public static void main(String[]args)throws Exception {
        Map<String,Object> entries=new TreeMap<>(Comparator.comparingInt(Integer::parseInt));
        for(Field field:eVi.class.getDeclaredFields())if(field.getType()==eVj.class) {
            field.setAccessible(true);eVj entry=(eVj)field.get(null);Map<String,Object> value=row(entry);
            if(value!=null && entries.put(Integer.toString(entry.d()),value)!=null)
                throw new IllegalStateException("Duplicate registry effect class"+entry.d());
        }
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("source","Installed wakfu-client.jar eVi/eWQ/eWR/eXE/eYO registry, offline reflection");
        result.put("client_jar_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of("client/lib/wakfu-client.jar")))));
        result.put("application_opcode",13497);result.put("removal_opcode",13560);
        result.put("effects",entries);
        Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(canonical(result))+"\n");
        System.out.println("Exported "+entries.size()+" native current-stat/null registry entries");
    }
}
