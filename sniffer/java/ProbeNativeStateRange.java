import java.util.*;
import java.lang.reflect.*;
import java.nio.file.Path;
/** Exercises real eLr constructor and Qf state matching; eKn range algorithm is probed separately. */
public class ProbeNativeStateRange {
    static ArrayList<alS> args(alS... values) {return new ArrayList<>(Arrays.asList(values));}
    static PV actor(long id) {
        return (PV) Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class,eHg.class},
            (p,m,a)->switch(m.getName()) {
                case "Sn"->id; case "bcM"->(byte)0;
                case "bcz","bcA"->0;case "bcB"->(short)0;case "bcy"->aAS.dyA;
                default->throw new UnsupportedOperationException(m.getName());
            });
    }
    static boolean match(ArrayList<alS> parameters,eZV effects) throws Exception {
        eLr query=new eLr(parameters);
        Method method=eLr.class.getDeclaredMethod("a",eHg.class,eZV.class);method.setAccessible(true);
        return (boolean)method.invoke(query,actor(22),effects);
    }
    public static void main(String[]unused) throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        fyZ.guX().a(new bbV());
        PV owner=actor(22);eZV effects=new eZV(owner);
        eZk carrier=eZk.a(null,owner,null,fyW.ae((short)3442,(short)1));carrier.dg(100);
        Field rows=Qf.class.getDeclaredField("bfT");rows.setAccessible(true);
        ((Map<Long,Qe>)rows.get(effects)).put(100L,carrier);
        if(!match(args(new alw(3),new amc("caster"),new alw(3442)),effects))throw new AssertionError("state match");
        if(!match(args(new alw(3),new amc("caster"),new alw(3442),new alw(1)),effects))throw new AssertionError("exact level1");
        if(match(args(new alw(3),new amc("caster"),new alw(3442),new alw(2)),effects))throw new AssertionError("exact level not threshold");
        if(match(args(new alw(3),new amc("caster"),new alw(3443)),effects))throw new AssertionError("other reference");
        eLr all=new eLr(args(new alw(3),new amc("caster"),new alw(3442),new alu(false),new amc("target")));
        Field alive=eJp.class.getDeclaredField("pXf");alive.setAccessible(true);
        eJp living=new eJp(args(new alw(3)));
        eJp allAllies=new eJp(args(new alw(0),new alw(3),new amc("caster"),new alu(false),new alu(false),new alu(false)));
        if (!(boolean)alive.get(living) || (boolean)alive.get(allAllies)) throw new AssertionError("ally default and optional inPlay");
        System.out.println("PASS eLr real Qf carrier reference/exact level; sfE="+ffe.sfE.aKg());
    }
}
