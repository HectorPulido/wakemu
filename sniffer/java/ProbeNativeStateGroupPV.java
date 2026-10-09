import java.lang.reflect.*;
/** Actual eYr.C/d: explicit null PV versus nonnull PV whose native bax is null. */
public final class ProbeNativeStateGroupPV {
    static void set(Object object, String name, Object value) throws Exception {
        for (Class<?> type=object.getClass();type!=null;type=type.getSuperclass()) {
            try { Field field=type.getDeclaredField(name);field.setAccessible(true);field.set(object,value);return; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    static Object zero(Class<?> type) {
        if(type==boolean.class)return false;
        if(type==byte.class)return (byte)0;
        if(type==short.class)return (short)0;
        if(type==int.class)return 0;
        if(type==long.class)return 0L;
        if(type==float.class)return 0F;
        if(type==double.class)return 0D;
        return null;
    }
    public static void main(String[] args) throws Exception {
        PV nullManager=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class[]{PV.class},
            (object,method,values)->zero(method.getReturnType()));
        int cases=0;
        for(int count:new int[]{7,9,10}) for(int constant:new int[]{-1,0,3}) {
            int[] parameters={0,0,1,0,1,0,12,0,1,constant};
            eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class[]{eVn.class},
                (object,method,values)-> {
                    if(method.getName().equals("fKJ"))return count;
                    if(method.getName().equals("a")&&values!=null&&values.length==3&&values[0] instanceof Integer)
                        return parameters[(Integer)values[0]];
                    if(method.getName().equals("w"))return (float)parameters[(Integer)values[0]];
                    return zero(method.getReturnType());
                });
            eYr runner=new eYr();runner.b(definition);runner.C(null);
            set(runner,"bfs",null);
            if(runner.d(null,false).Oh()!=-1)throw new AssertionError("null PV writes SP");
            set(runner,"bfs",nullManager);
            int expected=count>=10?constant:-1;
            if(runner.d(null,false).Oh()!=expected)throw new AssertionError("nonnull null-Qf loses constant");
            cases+=2;
        }
        System.out.println("Native eYr null-PV/null-Qf SP contract PASS "+cases+" cases");
    }
}
