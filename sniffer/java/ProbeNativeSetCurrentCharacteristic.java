import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Original eWX C/g/h and real fff setters, without native catalogs or a fight. */
public final class ProbeNativeSetCurrentCharacteristic {
    static void field(Object object, Class<?> owner, String name, Object value) throws Exception {
        Field field=owner.getDeclaredField(name);field.setAccessible(true);field.set(object,value);
    }
    static Object field(Object object, Class<?> owner, String name) throws Exception {
        Field field=owner.getDeclaredField(name);field.setAccessible(true);return field.get(object);
    }
    static Map<Integer,eWX> prototypes() throws Exception {
        Map<Integer,eWX> result=new TreeMap<>();
        for(Field field:eVi.class.getDeclaredFields()) {
            if(field.getType()!=eVj.class||!Modifier.isStatic(field.getModifiers()))continue;
            field.setAccessible(true);eVj entry=(eVj)field.get(null);
            if(entry.bkv() instanceof eWX runner)result.put(entry.d(),runner);
        }
        return result;
    }
    public static void main(String[]args)throws Exception {
        Gson gson=new GsonBuilder().serializeNulls().create();Map<Integer,eWX> entries=prototypes();
        if(args.length==1) {
            Map<String,Object> rows=new TreeMap<>();List<Object> unresolved=new ArrayList<>();
            for(var entry:entries.entrySet()) {
                eWX runner=entry.getValue();PC pc=runner.fNI();runner.bbx();
                if(pc==null){Map<String,Object> unknown=new LinkedHashMap<>();unknown.put("effect_class",entry.getKey());unknown.put("runner","eWX");unknown.put("fixed_stat_id",null);unknown.put("reason","Native prototype has null PC; no dynamic PC setter proven");unresolved.add(unknown);continue;}
                rows.put(entry.getKey().toString(),Map.of("runner","eWX","fixed_stat_id",pc.aKg()&255,"fixed_stat_name",pc.toString(),"numeric_kind",(int)pc.aZn(),"events",runner.bbw().stream().boxed().toList(),"bbA",runner.bbA(),"bbB",runner.bbB(),"bbz",runner.bbz(),"gain_event",((ffw)pc).fZx()?((ffw)pc).fZt():-1,"loss_event",((ffw)pc).fZy()?((ffw)pc).fZu():-1));
            }
            Files.writeString(Path.of(args[0]),gson.toJson(Map.of("source","Original eVi/eWX fixed PC and bbx","effects",rows,"unresolved_prototypes",unresolved))+"\n");
            System.out.println("PASS exported "+rows.size()+" original eWX families");return;
        }
        Method apply=eWX.class.getDeclaredMethod("g",PA.class);apply.setAccessible(true);
        Method remove=eWX.class.getDeclaredMethod("h",PA.class);remove.setAccessible(true);
        BufferedReader input=new BufferedReader(new InputStreamReader(System.in));
        for(String line;(line=input.readLine())!=null;) {
            JsonObject row=JsonParser.parseString(line).getAsJsonObject();int family=row.get("family").getAsInt();
            eWX runner=entries.get(family).fNS();ffw stat=(ffw)runner.fNI();
            int minimum=row.get("minimum").getAsInt(),maximum=row.get("maximum").getAsInt();
            fff characteristic=new fff(stat,minimum,maximum);
            field(characteristic,fff.class,"bqG",maximum);field(characteristic,fff.class,"bqF",minimum);
            characteristic.on(row.get("before").getAsInt());
            if(row.has("frozen")&&row.get("frozen").getAsBoolean())field(characteristic,fff.class,"sfT",true);
            int caster=row.get("caster").getAsInt();
            PV pv=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},(p,m,a)->m.getName().equals("c")?caster:null);
            field(runner,Qe.class,"bfr",pv);
            if(row.has("parameter")) {
                int parameter=row.get("parameter").getAsInt();
                Object definition=Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},(p,m,a)->switch(m.getName()){case "fKJ"->1;case "a"->parameter;default->null;});
                field(runner,Qe.class,"bfp",definition);
            }
            runner.C(null);int calculated=runner.getValue();apply.invoke(runner,characteristic);
            int after=characteristic.aYS(),value=runner.getValue(),delta=(Integer)field(runner,eWX.class,"rCE");
            field(characteristic,fff.class,"sfT",false);
            characteristic.on(row.has("intervening")?row.get("intervening").getAsInt():after);
            int removalBefore=characteristic.aYS();remove.invoke(runner,characteristic);
            System.out.println(gson.toJson(Map.of("family",family,"calculated",calculated,"after",after,"value",value,"delta",delta,"removal_before",removalBefore,"removed",characteristic.aYS())));
        }
    }
}
