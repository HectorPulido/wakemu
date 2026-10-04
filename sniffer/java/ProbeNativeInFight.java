import java.lang.reflect.Proxy;
import java.util.ArrayList;

public class ProbeNativeInFight {
    static eHg actor(boolean inFight) {
        return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},
            (proxy,method,args)->{if(method.getName().equals("dnz"))return inFight;
                throw new UnsupportedOperationException(method.getName());});
    }
    static eNZ criterion(String selector) {
        ArrayList<alS> parameters=new ArrayList<>();
        if(selector!=null)parameters.add(new amc(selector));
        return new eNZ(parameters);
    }
    public static void main(String[] args) {
        Object caster=actor(true),target=actor(false);
        if(criterion(null).a(caster,target,null,null)!=0)throw new AssertionError("default caster");
        if(criterion("target").a(caster,target,null,null)!=-1)throw new AssertionError("target false");
        if(criterion("target").a(caster,null,null,null)!=-1)throw new AssertionError("null target");
        System.out.println("eNZ IsInFight default/target/null PASS");
    }
}
