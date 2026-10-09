import java.lang.reflect.Proxy;
import java.util.ArrayList;
/** Original eMd/GS.cv against actual eHP/eHU contracts; no fight or data load. */
public final class ProbeNativeBreedInSymbiot {
    static Object actor(eHD[] slots) {
        eHU roster=(eHU)Proxy.newProxyInstance(eHU.class.getClassLoader(),new Class[]{eHU.class},
            (proxy,method,args)-> {
                if(method.getName().equals("Qn")) return slots[(Integer)args[0]];
                throw new UnsupportedOperationException(method.getName());
            });
        return Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class[]{eHg.class,eHP.class},
            (proxy,method,args)-> {
                if(method.getName().equals("drI")) return roster;
                throw new UnsupportedOperationException(method.getName());
            });
    }
    static boolean query(Object caster,Object target,long reference,String selector) {
        ArrayList<alS> args=new ArrayList<>();
        args.add(new alw(reference));args.add(new amc(selector));
        return new eMd(args).a(caster,target,null,null)==0;
    }
    public static void main(String[] arguments) {
        eHD[] occupied=new eHD[10];
        occupied[8]=new bPs((short)5347,"",1,(short)1,7L);
        occupied[9]=new bPs((short)32767,"",1,(short)1,7L);
        Object owner=actor(occupied),empty=actor(new eHD[10]);
        int checks=0;
        for(long reference:new long[]{Long.MIN_VALUE,-32768,-1,0,1152,5347,32767,32768,Long.MAX_VALUE})
            for(String selector:new String[]{"caster"," CASTER ","target"," TARGET ","unrecognized"}) {
                boolean actual=query(owner,empty,reference,selector);
                short normalized=GS.cv(reference);
                boolean expected=selector.trim().equalsIgnoreCase("caster")
                    && normalized>0 && (normalized==5347 || normalized==32767);
                if(actual!=expected) throw new AssertionError(reference+"/"+selector);
                checks++;
            }
        if(query(null,null,5347,"caster")) throw new AssertionError("null actor");
        System.out.println("PASS "+checks+" original eMd selector/slot/GS.cv cases plus null actor");
    }
}
