import java.lang.reflect.*;
/** Real1093 eZJ C/c and faq.SX on all three native resource runners. */
public class ProbeNativeFinalModifier {
    static void set(Object object,Class<?> type,String name,Object value)throws Exception {
        Field f=type.getDeclaredField(name);f.setAccessible(true);f.set(object,value);
    }
    public static void main(String[]args)throws Exception {
        eZJ modifier=new eZJ();modifier.lV(1093);
        eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},(p,m,a)->{
            if(m.getName().equals("a")&&a.length==3&&a[0]instanceof Integer)return 50;
            throw new UnsupportedOperationException(m.getName());
        });
        set(modifier,Qe.class,"bfp",definition);modifier.C(null);
        if(modifier.getValue()!=50)throw new AssertionError("parameter calculation");
        set(modifier,Qe.class,"bfD",true);
        Method apply=eZJ.class.getDeclaredMethod("c",Qe.class,boolean.class);apply.setAccessible(true);
        for(Qe source:new Qe[]{new eXt(),new eXs(),new eWx()}) {
            faq compatible=(faq)source;
            if(compatible.SX(0)!=0)throw new AssertionError("fresh nonzero");
            apply.invoke(modifier,source,false);
            if(compatible.SX(0)!=50)throw new AssertionError("modifier not accumulated");
            apply.invoke(modifier,source,false);
            if(compatible.SX(0)!=100)throw new AssertionError("modifier not additive");
            set(modifier,Qe.class,"bfD",false);apply.invoke(modifier,source,false);
            if(compatible.SX(0)!=100)throw new AssertionError("unexecutable mutated");
            set(modifier,Qe.class,"bfD",true);
        }
        apply.invoke(modifier,null,false);apply.invoke(modifier,new eXE(),false);
        eXt overflowing=new eXt();overflowing.SX(Integer.MAX_VALUE);
        apply.invoke(modifier,overflowing,false);
        if(overflowing.SX(0)!=Integer.MIN_VALUE+49)throw new AssertionError("int32 add");
        if(args.length>0) {
            cvY application=new cvY();
            if(!application.dp(java.nio.file.Files.readAllBytes(java.nio.file.Path.of(args[0]))) || application.eII()!=1093)
                throw new AssertionError("cvY1093 packet");
            eZJ received=new eZJ();received.lV(1093);
            iN wire=received.ds(application.eIJ());
            if(wire==null || received.LV()!=902 || received.getValue()!=50 || wire.Qs()!=411428
                    || wire.Qw()!=7 || wire.Qy()!=-7)
                throw new AssertionError("eZJ1093 decoded identity/value");
            System.out.println("PASS cvY1093 -> eZJ UID902 reference411428 value50 caster7 target-7");
        }
        System.out.println("PASS native1093 parameter0/additive faq eXt/eXs/eWx/executable/null/nonfaq/int32");
    }
}
