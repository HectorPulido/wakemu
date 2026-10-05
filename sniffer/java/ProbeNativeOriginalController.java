import java.lang.reflect.*;
import java.util.*;

/** eKc reads the listener Qe.bbc, not the rebound/triggering target. */
public class ProbeNativeOriginalController {
    static eHg actor(long controller) {
        return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class,PV.class},
            (p,m,a)->{if(m.getName().equals("dTD"))return controller;
                throw new UnsupportedOperationException(m.getName());});
    }
    static void check(eKc criterion,Object caster,Object target,Object runner,long expected)throws Exception {
        long actual=criterion.d(caster,target,runner,null);
        if(actual!=expected)throw new AssertionError(actual+" != "+expected);
    }
    public static void main(String[]args)throws Exception {
        eKc criterion=new eKc(new ArrayList<alS>());
        eHg original=actor(91),rebound=actor(202);
        eXE listener=new eXE();
        Field field=Qe.class.getDeclaredField("bfs");field.setAccessible(true);
        field.set(listener,original);
        check(criterion,original,rebound,null,0);
        check(criterion,original,rebound,listener,91);
        check(criterion,rebound,original,listener,91);
        field.set(listener,null);
        check(criterion,original,rebound,listener,0);
        check(criterion,original,rebound,rebound,202);
        System.out.println("eKc original Qe target/null/eHg and rebound distinction: 5 PASS");
    }
}
