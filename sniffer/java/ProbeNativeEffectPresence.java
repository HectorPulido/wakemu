import java.lang.reflect.Proxy;
import java.util.ArrayList;

public class ProbeNativeEffectPresence {
    static eHg actor(Qf manager) {
        return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},
            (proxy,method,args)->{if(method.getName().equals("bax"))return manager;
                throw new UnsupportedOperationException(method.getName());});
    }
    static eMj criterion(String selector,int reference) {
        ArrayList<alS> parameters=new ArrayList<>();
        parameters.add(new amc(selector));parameters.add(new alw(reference));
        return new eMj(parameters);
    }
    public static void main(String[] args) throws Exception {
        ProbeNativeDispel.Manager manager=new ProbeNativeDispel.Manager();
        eXE effect=new eXE();
        ProbeNativeDispel.set(effect,Qe.class,"bfp",ProbeNativeDispel.definition(308267,400,2,true,new int[]{}));
        manager.effects.add(effect);
        Object caster=actor(new ProbeNativeDispel.Manager()),target=actor(manager);
        if(criterion("target",308267).a(caster,target,null,null)!=0)throw new AssertionError("definition ID");
        if(criterion("target",400).a(caster,target,null,null)!=-1)throw new AssertionError("not action class");
        if(criterion("caster",308267).a(caster,target,null,null)!=-1)throw new AssertionError("caster manager");
        manager.effects.clear();
        if(criterion("target",308267).a(caster,target,null,null)!=-1)throw new AssertionError("removed effect");
        System.out.println("eMj/Qf.oG generic definition presence/owner/removal PASS");
    }
}
