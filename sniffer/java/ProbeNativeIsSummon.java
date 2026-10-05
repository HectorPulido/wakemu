import java.lang.reflect.*;import java.util.*;
public class ProbeNativeIsSummon {
 static eHg actor(boolean summon){return(eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},(p,m,a)->switch(m.getName()){case "dTE"->summon;default->throw new UnsupportedOperationException(m.getName());});}
 static void check(String selector,Object caster,Object target,int expected){eOT condition=new eOT(new ArrayList<alS>(List.of(new amc(selector))));int actual=condition.a(caster,target,null,null);if(actual!=expected)throw new AssertionError(selector+":"+actual+"/"+expected);System.out.println("PASS "+selector+" nativeSentinel="+actual);}
 public static void main(String[]args){eHg caster=actor(false),target=actor(true);check("caster",caster,target,-1);check("target",caster,target,0);check("TaRgEt",caster,target,0);check("invalid",caster,target,-1);check("target",caster,null,-1);check("caster",null,target,-1);check("triggeringCaster",caster,target,-1);check("target",caster,actor(false),-1);}
}
