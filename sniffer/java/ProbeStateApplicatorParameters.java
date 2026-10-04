import java.nio.file.*;
import java.lang.reflect.*;
import com.google.gson.*;
/** Native304 C/fNa using an actual exported effect, not a invented layout. */
public class ProbeStateApplicatorParameters {
    static class Applicator extends eWu {
        @Override public short fRR(){return 1;}
        int probability(){return fNa();}
        int reference(){return kFB;}
        int level(){return rBo;}
    }
    public static void main(String[] args)throws Exception {
        JsonObject catalog=JsonParser.parseReader(Files.newBufferedReader(Path.of("server/protocol/spell-effect-trees.json"))).getAsJsonObject();
        JsonObject effect=catalog.getAsJsonObject("effects").getAsJsonObject("167716");
        JsonArray values=effect.getAsJsonArray("parameters_by_level").get(0).getAsJsonArray();
        int[] parameters=new int[values.size()];for(int i=0;i<parameters.length;i++)parameters[i]=values.get(i).getAsInt();
        eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(proxy,m,a)->switch(m.getName()){
            case "a"->parameters[(int)a[0]];case "fKJ"->parameters.length;default->throw new UnsupportedOperationException(m.getName());});
        Applicator runner=new Applicator();Field f=Qe.class.getDeclaredField("bfp");f.setAccessible(true);f.set(runner,definition);
        runner.C(null);
        if(runner.reference()!=3896 || runner.level()!=1 || runner.probability()!=100)throw new AssertionError("Native actual304 contract");
        Object registered=eVi.fLJ().pS(304);
        if(!(registered instanceof eWu))throw new AssertionError("Native304 runner");
        System.out.println("actual effect167716: [3896,1,-1] -> eWu state3896 level1 application chance100");
        parameters[0]=65536+3896;parameters[1]=65537;runner.C(null);
        if(runner.reference()!=3896 || runner.level()!=1)throw new AssertionError("native short narrowing");
        parameters[2]=-2;
        if(runner.probability()!=0)throw new AssertionError("native -2 sentinel");
        System.out.println("native reference/level short narrowing; -2 sentinel probability0 (runtime still unsupported)");
    }
}
