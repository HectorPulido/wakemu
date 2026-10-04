import java.util.*;
/** Isolate native PT counting from graphical notifications and event callbacks. */
public class ProbeEffectSuccess {
    static class Null extends eXE {
        public void d(Qe trigger,boolean immediate) {}
        public void dr(byte... channels) {}
        public void aX(boolean decrement) {}
        protected void bbY() {}
    }
    static class Gain extends eWQ {
        Gain(){super(ffw.sgQ);}
        public void d(Qe trigger,boolean immediate) {}
        public void dr(byte... channels) {}
        public void aX(boolean decrement) {}
        protected void bbY() {}
    }
    static class Loss extends eWR {
        Loss(){super(ffw.sgQ);}
        public void d(Qe trigger,boolean immediate) {}
        public void dr(byte... channels) {}
        public void aX(boolean decrement) {}
        protected void bbY() {}
    }
    public static void main(String[]args)throws Exception {
        eXE fresh=new eXE();fresh.C(null);
        if(fresh.cYh()!=-1)throw new AssertionError("fresh null status must remain-1");
        System.out.println("native fresh eXE400 parameterless status=-1 (preserves initial status)");
        for(int status:new int[]{-1,0,7}) {
            Null effect=new Null();effect.fc((byte)status);PT outcome=new PT();
            ProbeStatEffects.assign(effect,Qe.class,"bfN",outcome);
            effect.a(null,false);
            if(outcome.bas()!=1)throw new AssertionError("null status does not determine PT count");
            System.out.println("null status"+status+" -> PT.bas="+outcome.bas());
        }
        for(eWW effect:new eWW[]{new Gain(),new Loss()}) {
            Map<PC,fff> stats=new HashMap<>();fff characteristic=new fff(ffw.sgQ,0,100);characteristic.or(100);
            characteristic.on(effect instanceof eWQ?100:0);stats.put(ffw.sgQ,characteristic);
            ProbeStatEffects.assign(effect,Qe.class,"bfs",ProbeCombatArithmetic.actor(stats,1));
            ProbeStatEffects.assign(effect,Qe.class,"aSg",20);PT outcome=new PT();
            ProbeStatEffects.assign(effect,Qe.class,"bfN",outcome);
            effect.a(null,false);
            if(effect.getValue()!=0 || outcome.bas()!=1)throw new AssertionError("zero actual delta must still count execution");
            System.out.println(effect.getClass().getSimpleName()+" requested20 actual0 -> PT.bas="+outcome.bas());
            if(effect.bbH())throw new AssertionError("eWW initial zero rejected by bbH");
        }
    }
}
