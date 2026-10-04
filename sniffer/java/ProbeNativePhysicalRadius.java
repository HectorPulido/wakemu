import java.lang.reflect.Proxy;
import java.util.ArrayList;

public class ProbeNativePhysicalRadius {
    static eHg actor(byte radius) {
        return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},
            (proxy,method,args)->{if(method.getName().equals("bcL"))return radius;
                throw new UnsupportedOperationException(method.getName());});
    }
    static eKV criterion(String selector) {
        ArrayList<alS> parameters=new ArrayList<>();parameters.add(new amc(selector));
        return new eKV(parameters);
    }
    public static void main(String[] args) {
        Object caster=actor((byte)0),target=actor((byte)2);
        if(criterion("caster").d(caster,target,null,null)!=0)throw new AssertionError("caster");
        if(criterion("target").d(caster,target,null,null)!=2)throw new AssertionError("target");
        if(criterion("target").d(caster,null,null,null)!=-1)throw new AssertionError("missing actor");
        if(criterion("target").d(caster,actor((byte)-128),null,null)!=-128)throw new AssertionError("signed byte");
        System.out.println("eKV GetPhysicalRadius caster/target/null/signed PASS");
    }
}
