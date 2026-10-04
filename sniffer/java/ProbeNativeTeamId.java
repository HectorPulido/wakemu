import java.lang.reflect.Proxy;
import java.util.ArrayList;

public class ProbeNativeTeamId {
    static eHg actor(byte affiliation) {
        return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},
            (proxy,method,args)-> { if(method.getName().equals("bcM"))return affiliation;
                throw new UnsupportedOperationException(method.getName()); });
    }
    static eLx criterion(String selector) {
        ArrayList<alS> parameters=new ArrayList<>();
        if(selector!=null)parameters.add(new amc(selector));
        return new eLx(parameters);
    }
    public static void main(String[] args) {
        Object caster=actor((byte)-128),target=actor((byte)127);
        if(criterion(null).d(caster,target,null,null)!=-128)throw new AssertionError("default caster");
        if(criterion("target").d(caster,target,null,null)!=127)throw new AssertionError("target");
        if(criterion("target").d(caster,null,null,null)!=-1)throw new AssertionError("missing actor");
        System.out.println("eLx GetTeamId signed bcM default/target/missing PASS");
    }
}
