import java.lang.reflect.*;
/** Installed eZC/eZD return the original non-Qq PV even with owner flag one. */
public final class ProbeNativeTeleportOwnerParameter {
    private static void field(Object object, String name, Object value) throws Exception {
        for (Class<?> type=object.getClass(); type!=null; type=type.getSuperclass()) {
            try { Field field=type.getDeclaredField(name); field.setAccessible(true);
                field.set(object,value); return; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    public static void main(String[] args) throws Exception {
        PV recipient=(PV)Proxy.newProxyInstance(PV.class.getClassLoader(),new Class<?>[]{PV.class},
            (proxy,method,values)-> { throw new AssertionError(method.getName()); });
        for (Class<?> type:new Class<?>[]{eZC.class,eZD.class}) for(int flag:new int[]{0,1}) {
            final int ownerFlag=flag;
            eVn definition=(eVn)Proxy.newProxyInstance(eVn.class.getClassLoader(),new Class<?>[]{eVn.class},
                (proxy,method,values)-> {
                    if(method.getName().equals("fKJ"))return 1;
                    if(method.getName().equals("a") && method.getReturnType()==int.class)return ownerFlag;
                    throw new AssertionError(method.getName());
                });
            Object runner=type.getConstructor().newInstance();field(runner,"bfp",definition);
            field(runner,type==eZC.class?"bfr":"bfs",recipient);
            Method select=type.getDeclaredMethod("fRz");select.setAccessible(true);
            if(select.invoke(runner)!=recipient)throw new AssertionError("Original PV changed");
        }
        System.out.println("PASS installed eZC/eZD non-Qq recipient flags0/1 rows=4");
    }
}
