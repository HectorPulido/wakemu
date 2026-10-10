import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

import com.google.gson.*;

/** Native class-scoped typed metadata graph; no runner execution or combat state. */
public class ExportClassMechanicGraph {
    static final Gson GSON = new GsonBuilder().serializeNulls().create();
    static final Map<Integer,int[]> GROUPS = new HashMap<>();
    static final Map<Integer,String> CRITERIA = new HashMap<>();
    static final Map<Integer,aNv> STATES = new HashMap<>();
    static final Map<Integer,aKa> AREAS = new HashMap<>();
    static final Set<String> SEEN = new HashSet<>();
    static final ArrayDeque<String> QUEUE = new ArrayDeque<>();
    static final Map<String,Integer> COUNTS = new TreeMap<>();
    static JsonObject profiles;
    static BufferedWriter output;

    static Object cloneArray(Object value) {
        if(value==null || !value.getClass().isArray())return value;
        int size=Array.getLength(value);Object copy=Array.newInstance(value.getClass().getComponentType(),size);
        for(int index=0;index<size;index++)Array.set(copy,index,cloneArray(Array.get(value,index)));
        return copy;
    }
    static <T> T snapshotRecord(T value) {
        try {
            Constructor<?> constructor=value.getClass().getDeclaredConstructor();constructor.setAccessible(true);
            Object result=constructor.newInstance();
            for(Class<?> type=value.getClass();type!=null && type!=Object.class;type=type.getSuperclass())for(Field field:type.getDeclaredFields()) {
                if(Modifier.isStatic(field.getModifiers()) || field.isSynthetic())continue;
                field.setAccessible(true);field.set(result,cloneArray(field.get(value)));
            }
            return (T)result;
        } catch(ReflectiveOperationException error) {throw new IllegalStateException("Cannot snapshot native bdata record",error);}
    }
    static void enqueue(String kind, int reference) { QUEUE.add(kind + ":" + reference); }
    static void write(Map<String,Object> row) throws IOException {
        output.write(GSON.toJson(row)); output.newLine();
        COUNTS.merge((String)row.get("kind"), 1, Integer::sum);
    }
    static Map<String,Object> row(String kind, int id) {
        Map<String,Object> row = new LinkedHashMap<>();
        row.put("kind", kind); row.put("reference", id); return row;
    }
    static List<Integer> levels(int minimum, int maximum) {
        Set<Integer> levels = new TreeSet<>();
        for(int level=0; level<=245; level++) levels.add(level);
        for(int level:new int[]{-32768,-1,minimum,minimum-1,maximum,maximum+1,32767})
            if(level>=Short.MIN_VALUE && level<=Short.MAX_VALUE) levels.add(level);
        return new ArrayList<>(levels);
    }
    static Object raw(Object object, int depth, IdentityHashMap<Object,Boolean> visited) {
        if(object==null || object instanceof Number || object instanceof Boolean || object instanceof String || object instanceof Character) return object;
        if(object instanceof Enum<?> value) return Map.of("native_enum_class",object.getClass().getName(),"constant",value.name(),"ordinal",value.ordinal());
        if(object instanceof BitSet bits) return bits.stream().toArray();
        if(visited.put(object, Boolean.TRUE)!=null) return Map.of("native_class",object.getClass().getName(),"unexpanded","cycle_or_shared_identity");
        if(object.getClass().isArray()) {
            List<Object> result=new ArrayList<>();
            for(int index=0;index<Array.getLength(object);index++) result.add(raw(Array.get(object,index),depth-1,visited));
            return result;
        }
        if(object instanceof Collection<?> values) {
            List<Object> result=new ArrayList<>();for(Object value:values)result.add(raw(value,depth-1,visited));return result;
        }
        Map<String,Object> result=new LinkedHashMap<>();result.put("native_class",object.getClass().getName());
        if(depth<0) {result.put("unexpanded","depth_limit");return result;}
        Map<String,Object> fields=new TreeMap<>();
        for(Class<?> type=object.getClass();type!=null && type!=Object.class;type=type.getSuperclass()) {
            for(Field field:type.getDeclaredFields()) {
                if(Modifier.isStatic(field.getModifiers()) || field.isSynthetic())continue;
                String key=type.getName()+"."+field.getName();
                try {field.setAccessible(true);fields.put(key,raw(field.get(object),depth-1,visited));}
                catch(RuntimeException | IllegalAccessException error) {fields.put(key,Map.of("unexpanded",error.getClass().getName()));}
            }
        }
        result.put("native_fields",fields);return result;
    }
    static Object raw(Object value) {return raw(value,8,new IdentityHashMap<>());}
    static Object definition(Object value) {return raw(value,1,new IdentityHashMap<>());}
    static List<Integer> roots(Iterator<eVn> iterator) {
        List<Integer> roots=new ArrayList<>();while(iterator.hasNext()) {int id=iterator.next().aZE();roots.add(id);enqueue("effect",id);}return roots;
    }
    static void spell(int id) throws Exception {
        fyF spell=bPS.elL().IP(id);
        Map<String,Object> row=row("spell",id);
        if(spell==null){row.put("native_missing",true);write(row);return;}
        Field field=fyF.class.getDeclaredField("twf");field.setAccessible(true);fyP casting=(fyP)field.get(spell);
        row.put("native_class",spell.getClass().getName());row.put("maximum_level",spell.Fq());
        row.put("native_casting_definition",definition(casting));row.put("native_cast_criterion",raw(spell.gtP()));
        Map<String,Object> samples=new LinkedHashMap<>();
        for(int level:levels(0,spell.Fq())) samples.put(Integer.toString(level),roots(spell.fG((short)level)));
        row.put("root_samples",samples);row.put("protected",spell.elO());write(row);
    }
    static void state(int id) throws Exception {
        Map<String,Object> row=row("state",id);aNv definition=STATES.get(id);fyW state=fyZ.guX().aax(id);
        if(state==null || definition==null){row.put("native_missing",true);write(row);return;}
        if(definition.d()!=id)throw new AssertionError("State record identity");
        row.put("native_definition",definition(definition));row.put("native_container",definition(state));
        List<Integer> rawRoots=new ArrayList<>();if(definition.cku()!=null)for(int effect:definition.cku()){rawRoots.add(effect);enqueue("effect",effect);}row.put("raw_roots",rawRoots);
        Map<String,Object> samples=new LinkedHashMap<>();
        for(int level:levels(0,definition.aWa())) {
            fyW selected=state.cu((short)level);
            samples.put(Integer.toString(level),Map.of("selected_level",(int)selected.cmZ(),"duration",selected.gtL(),"realtime_duration",selected.guH(),"skip_turn_timer",selected.cxj(),"roots",roots(selected.fH(selected.cmZ()).iterator())));
        }
        row.put("level_samples",samples);write(row);
    }
    static void area(int id) throws Exception {
        Map<String,Object> row=row("area",id);aKa definition=AREAS.get(id);
        if(definition==null){row.put("native_missing",true);write(row);return;}
        if(definition.d()!=id)throw new AssertionError("Area record identity");
        row.put("native_definition",definition(definition));faV area=bcN.hFx.a(definition);
        row.put("native_prototype",definition(area));List<Integer> roots=new ArrayList<>();
        if(definition.cku()!=null)for(int effect:definition.cku()){roots.add(effect);enqueue("effect",effect);}row.put("raw_roots",roots);
        row.put("entry_masks",definition.ckB());row.put("exit_masks",definition.ckC());row.put("removal_masks",definition.ckD());row.put("area_properties",definition.ckE());row.put("type",definition.aMO());write(row);
    }
    static void profile(int id) throws Exception {
        Map<String,Object> row=row("profile",id);JsonElement profile=profiles.get(Integer.toString(id));
        if(profile==null){row.put("native_missing",true);row.put("reason","outside_class_scoped_native_profile_export");write(row);return;}
        row.put("native_ability_profile",profile);
        for(JsonElement ability:profile.getAsJsonObject().getAsJsonArray("abilities"))enqueue("spell",ability.getAsJsonObject().get("reference").getAsInt());write(row);
    }
    static boolean nativeAreaReferenceRunner(Object runner) throws ReflectiveOperationException {
        // eYS changes source-caster selection, but inherits the same eYQ.C slot0.
        // Reject descendants overriding C instead of guessing a parameter contract.
        return runner instanceof eYQ && runner.getClass().getMethod("C", Qe.class).getDeclaringClass()==eYQ.class;
    }
    static void effect(int id) throws Exception {
        Map<String,Object> row=row("effect",id);eVn effect=bcA.dcX().AH(id);
        if(effect==null){row.put("native_missing",true);write(row);return;}
        row.put("family",effect.awM());row.put("criterion_raw",CRITERIA.getOrDefault(id,""));row.put("criterion_native",raw(effect.fKT()));
        row.put("native_metadata",ExportClassSummonEffectTrees.metadata(effect));
        row.put("native_definition",definition(effect));
        UI<eZR> registration=eVi.fLJ().pR(effect.awM());
        row.put("native_runner_class",registration==null?null:registration.bkv().getClass().getName());
        row.put("native_registration",definition(registration));
        List<Integer> children=new ArrayList<>();for(int child:GROUPS.getOrDefault(id,new int[0])){children.add(child);enqueue("effect",child);}row.put("children_ordered",children);
        row.put("event_target_code",(int)effect.aZV().aKg());row.put("event_caster_code",effect.aZW()==null?null:(int)effect.aZW().aKg());
        row.put("subscription",effect.aZN());row.put("owner_on_caster",effect.aZA());row.put("reverse_subscription",effect.aZw());row.put("global_subscription",effect.aZx());row.put("event_priority",effect.aZM());row.put("event_execution_count",(int)effect.aZS());row.put("event_execution_count_per_level",effect.cyc());row.put("suppresses_level_one",effect.aZB());
        row.put("minimum_level",effect.fKR());row.put("maximum_level",effect.fKS());row.put("raw_parameters",effect.fKI());
        Map<String,Object> samples=new LinkedHashMap<>();List<Map<String,Object>> references=new ArrayList<>();
        String referenceKind=registration!=null && nativeAreaReferenceRunner(registration.bkv()) ? "area" : switch(effect.awM()){case 304->"state";case 649->"spell";case 307->"profile";default->null;};
        int referenceSlot=effect.awM()==649 ? 2 : 0;
        for(int level:levels(effect.fKR(),effect.fKS())) {
            List<Integer> parameters=new ArrayList<>();for(int index=0;index<effect.fKJ();index++)parameters.add(effect.a(index,(short)level,eVh.rpA));
            Map<String,Object> sample=new LinkedHashMap<>();sample.put("parameters",parameters);sample.put("probability",effect.eg((short)level));sample.put("timing",ExportEffectRuntimeMetadata.timing(effect,(short)level));samples.put(Integer.toString(level),sample);
            if(referenceKind!=null && parameters.size()>referenceSlot) {
                int target=parameters.get(referenceSlot);references.add(Map.of("kind",referenceKind,"reference",target,"sample_level",level,"parameter_slot",referenceSlot,"native_evaluation_mode","eVh.rpA"));
                // Boundary/negative samples are observations, not executable scope.
                if(level>=0 && level<=245 && target>0)enqueue(referenceKind,target);
            }
        }
        row.put("samples",samples);row.put("classified_reference_samples",references);
        row.put("reference_semantics",referenceKind==null?"not_classified_by_this_exporter":"native_reference_slot_contract_304_eYQ_307_slot0_649_slot2");
        row.put("dynamic_reachability","unknown_no_runner_or_criterion_execution");write(row);
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=2)throw new IllegalArgumentException("seed-json output-jsonl.gz");
        JsonObject seeds=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        profiles=JsonParser.parseString(Files.readString(Path.of("server/protocol/native-class-summon-abilities.json"))).getAsJsonObject().getAsJsonObject("profiles");
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX record){GROUPS.put(record.d(),record.cku());}});
        apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw record){CRITERIA.put(record.aZE(),record.cyi());}});
        apw.bGL().a(new aNv(),new apB<aNv>(){public void load(aNv record){STATES.put(record.d(),snapshotRecord(record));}});
        apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa record){AREAS.put(record.d(),snapshotRecord(record));}});
        fyZ.guX().a(new bbV());
        for(var entry:STATES.entrySet())if(entry.getKey()!=entry.getValue().d())throw new AssertionError("State snapshot identity drift");
        for(var entry:AREAS.entrySet())if(entry.getKey()!=entry.getValue().d())throw new AssertionError("Area snapshot identity drift");
        Path target=Path.of(args[1]),temporary=target.resolveSibling(target.getFileName()+".tmp");
        try(BufferedWriter writer=new BufferedWriter(new OutputStreamWriter(new java.util.zip.GZIPOutputStream(Files.newOutputStream(temporary)),java.nio.charset.StandardCharsets.UTF_8))) {
            output=writer;
            for(String kind:new String[]{"spell","state","profile"})for(JsonElement id:seeds.getAsJsonArray(kind))enqueue(kind,id.getAsInt());
            while(!QUEUE.isEmpty()) {
                String key=QUEUE.removeFirst();if(!SEEN.add(key))continue;
                int split=key.indexOf(':');String kind=key.substring(0,split);int id=Integer.parseInt(key.substring(split+1));
                try {switch(kind){case "spell"->spell(id);case "state"->state(id);case "profile"->profile(id);case "area"->area(id);case "effect"->effect(id);default->throw new IllegalStateException(kind);}}
                catch(Exception error) {Map<String,Object> failed=row(kind,id);failed.put("native_export_exception",error.toString());failed.put("reachability","unknown");write(failed);System.out.println("Native unknown "+key+" "+error);}
                if(SEEN.size()%500==0)System.out.println("Exported nodes="+SEEN.size()+" counts="+COUNTS);
            }
        }
        Files.move(temporary,target,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        System.out.println("PASS native typed graph "+COUNTS);
    }
}
