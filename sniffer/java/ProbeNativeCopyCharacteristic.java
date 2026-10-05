import java.lang.reflect.*;
import java.util.*;
/** Actual eWZ setters and additional data against native PA, no game session. */
public class ProbeNativeCopyCharacteristic {
    static void set(Object o, Class<?> c, String n, Object v) throws Exception {
        Field f=c.getDeclaredField(n); f.setAccessible(true); f.set(o,v);
    }
    static void check(int copiedCurrent,int copiedMaximum,int expectedCurrent,int expectedMaximum) throws Exception {
        fff source=new fff(ffw.sgF,0,6);source.or(6);source.on(2);
        fff target=new fff(ffw.sgF,0,6);target.or(6);target.on(1);
        eWZ effect=new eWZ();
        set(effect,Qe.class,"bfr",ProbeCombatArithmetic.actor(Map.of(ffw.sgF,source),1));
        set(effect,Qe.class,"bfs",ProbeCombatArithmetic.actor(Map.of(ffw.sgF,target),2));
        set(effect,Qe.class,"aSg",copiedCurrent);
        set(effect,eWZ.class,"pJt",(byte)4);
        set(effect,eWZ.class,"ddL",copiedMaximum);
        Method apply=eWZ.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);apply.invoke(effect,null,true);
        if(target.aYS()!=expectedCurrent || target.aYU()!=expectedMaximum)throw new AssertionError(target.aYS()+"/"+target.aYU());
        effect.bbR();
        if(target.aYS()!=expectedCurrent || target.aYU()!=expectedMaximum)throw new AssertionError("Removal reverted copy");
    }
    static void calculate(int current,int maximum,int ratio,int expectedCurrent,int expectedMaximum)throws Exception {
        fff resource=new fff(ffw.sgF,0,6);resource.or(maximum);resource.on(current);
        eWZ effect=new eWZ();
        eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
            (proxy,method,args)->switch(method.getName()) {
                case "fKJ" -> 2;
                case "a" -> (int)args[0]==0?4:ratio;
                default -> throw new UnsupportedOperationException(method.getName());
            });
        set(effect,Qe.class,"bfp",definition);
        set(effect,Qe.class,"bfD",true);
        set(effect,Qe.class,"bfr",ProbeCombatArithmetic.actor(Map.of(ffw.sgF,resource),1));
        set(effect,Qe.class,"bfs",ProbeCombatArithmetic.actor(Map.of(ffw.sgF,resource),2));
        effect.bbE();
        System.out.println("copy additional="+HexFormat.of().formatHex(ij.MR().em(4).ek(expectedMaximum).MX().toByteArray()));
        Field field=eWZ.class.getDeclaredField("ddL");field.setAccessible(true);
        if(effect.getValue()!=expectedCurrent || field.getInt(effect)!=expectedMaximum)
            throw new AssertionError("Computed copy "+effect.getValue()+"/"+field.getInt(effect));
    }
    public static void main(String[] args)throws Exception{
        calculate(2,6,100,2,6);calculate(2,6,50,1,3);calculate(2,6,0,0,0);
        check(4,5,4,5);check(9,3,3,3);check(-3,-2,0,0);check(9,9,6,6);
        System.out.println("Native eWZ: max then current setters clamp; removal does not reverse copied values.");
    }
}
