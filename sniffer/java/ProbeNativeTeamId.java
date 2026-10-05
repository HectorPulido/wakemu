import java.lang.reflect.Proxy;
import java.util.ArrayList;

public class ProbeNativeTeamId {
    static eHg actor(byte affiliation) {
        return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class, PV.class},
            (proxy,method,args)-> { if(method.getName().equals("bcM"))return affiliation;
                throw new UnsupportedOperationException(method.getName()); });
    }
    static eLx criterion(String selector) {
        ArrayList<alS> parameters=new ArrayList<>();
        if(selector!=null)parameters.add(new amc(selector));
        return new eLx(parameters);
    }
    public static void main(String[] args) throws Exception {
        Object caster=actor((byte)-128),target=actor((byte)127);
        if(criterion(null).d(caster,target,null,null)!=-128)throw new AssertionError("default caster");
        if(criterion("target").d(caster,target,null,null)!=127)throw new AssertionError("target");
        if(criterion("target").d(caster,null,null,null)!=-1)throw new AssertionError("missing actor");
        eXE source=new eXE(), listener=new eXE();
        java.lang.reflect.Field context=Qe.class.getDeclaredField("bfu");context.setAccessible(true);context.set(listener,eVt.a(false,false,source));
        java.lang.reflect.Field casterField=Qe.class.getDeclaredField("bfr");casterField.setAccessible(true);casterField.set(source,target);
        java.lang.reflect.Field targetField=Qe.class.getDeclaredField("bfs");targetField.setAccessible(true);targetField.set(source,caster);
        if(criterion("triggeringCaster").d(caster,target,listener,null)!=127)throw new AssertionError("source caster team");
        if(criterion("TRIGGERINGTARGET").d(caster,target,listener,null)!=-128)throw new AssertionError("source target team");
        if(criterion("triggeringCaster").d(caster,target,null,null)!=-1)throw new AssertionError("source absent");
        if(criterion("unknown").d(caster,target,listener,null)!=-1)throw new AssertionError("unknown selector null");
        System.out.println("eLx GetTeamId signed bcM default/target/missing PASS");
    }
}
