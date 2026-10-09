import java.lang.reflect.*;
import java.nio.file.Path;
import java.util.*;
import com.google.gson.Gson;

/** Original Qq object identity and fee visual gate choice, offline only. */
public final class ProbeNativePortalIdentity {
    static class Owner extends biw {
        public byte bcM() { return 0; }
        public long Sn() { return 7; }
        public Qf bax() { return null; }
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        final faV[] template=new faV[1];
        apw.bGL().a(new aKa(),new apB<aKa>() {
            public void load(aKa data) { if(data.d()==823) template[0]=bcN.hFx.a(data); }
        });
        if(template[0]==null) throw new AssertionError("Missing native gate");
        fee evaluator=new fee();
        Field entries=fee.class.getDeclaredField("sbm"), exits=fee.class.getDeclaredField("sbn");
        entries.setAccessible(true);exits.setAccessible(true);
        Set<Qq> input=(Set<Qq>)entries.get(evaluator);
        Map<Qq,Set<fyJ>> output=(Map<Qq,Set<fyJ>>)exits.get(evaluator);
        List<Object> nodes=new ArrayList<>();
        for(int n=0;n<32;n++) {
            Owner owner=new Owner();
            faV gate=template[0].b(new fbm(1000+n,n,0,(short)0,null,7,owner,(short)1,aAS.wL(3)));
            if(gate.getClass().getMethod("hashCode").getDeclaringClass()!=Object.class
                || gate.getClass().getMethod("equals",Object.class).getDeclaringClass()!=Object.class)
                throw new AssertionError("Gate overrides native object identity");
            if(n<16) input.add(gate);
            Set<fyJ> failures=new HashSet<>();if(n%4!=0) failures.add(fyJ.twI);
            output.put(gate,failures);
            nodes.add(Arrays.asList(gate.Sn(),gate.hashCode(),System.identityHashCode(gate),n<16,n%4==0));
        }
        List<Long> inputOrder=new ArrayList<>(),outputOrder=new ArrayList<>(),validOutput=new ArrayList<>();
        for(Qq gate:input) inputOrder.add(gate.Sn());
        for(Map.Entry<Qq,Set<fyJ>> row:output.entrySet()) {
            outputOrder.add(row.getKey().Sn());if(row.getValue().isEmpty())validOutput.add(row.getKey().Sn());
        }
        if(evaluator.cXm().Sn()!=inputOrder.get(0)||evaluator.cXn().Sn()!=validOutput.get(0))
            throw new AssertionError("fee choice differs from actual map/set iteration");
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("schema","native-portal-identity-v1");result.put("nodes",nodes);
        result.put("entry_iteration",inputOrder);result.put("exit_iteration",outputOrder);
        result.put("valid_exit_iteration",validOutput);
        result.put("selected_entry",evaluator.cXm().Sn());result.put("selected_exit",evaluator.cXn().Sn());
        result.put("hashCode_declaring_class","java.lang.Object");
        result.put("equals_declaring_class","java.lang.Object");
        System.out.println(new Gson().toJson(result));
    }
}
