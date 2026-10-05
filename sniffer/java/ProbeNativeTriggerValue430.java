import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/** Execute installed source-runner mutation; distinguish damage from healing. */
public class ProbeNativeTriggerValue430 {
    static void check(Qe runner, int initial, int mode, float amount,
                      boolean replace, int expected) throws Exception {
        Field value = Qe.class.getDeclaredField("aSg");
        value.setAccessible(true);
        value.setInt(runner, initial);
        runner.a(mode, amount, replace);
        int actual = runner.getValue();
        if (actual != expected) throw new AssertionError(
            runner.getClass().getName() + " mode=" + mode + " got=" + actual);
    }
    public static void main(String[] arguments) throws Exception {
        if (arguments.length > 0) {
            for (String name : arguments) {
                Class<?> runner = Class.forName(name, false, Qe.class.getClassLoader());
                System.out.println(name + " " + runner.getMethod("a", int.class,
                    float.class, boolean.class).getDeclaringClass().getName());
            }
            return;
        }
        check(new eXt(), 100, 0, 25, false, 125);
        check(new eXt(), 100, 0, 25, true, 25);
        check(new eXt(), 100, 1, -150, false, 0);
        check(new eXt(), 100, 1, 17, true, 17);
        check(new eXs(), 3, 0, -50, false, 1);
        check(new eXs(), -3, 0, 50, true, -2);
        check(new eXs(), 3, 1, -1.5f, true, -2);
        check(new eXs(), 3, 1, -4.5f, false, -1);
        check(new eWx(), 100, 0, 25, false, 125);
        check(new eWx(), 100, 0, 25, true, 100);
        check(new eWx(), 100, 1, 17, true, 17);
        check(new eWx(), 100, 1, -150, false, -50);
        eXt auxiliary = new eXt();
        for (int mode : new int[] {5,6}) {
            Field field = eXt.class.getDeclaredField(mode==5 ? "rDy" : "rDz");
            field.setAccessible(true);
            auxiliary.a(mode, 20, false);
            auxiliary.a(mode, 7, false);
            if(field.getInt(auxiliary)!=7 || auxiliary.getValue()!=0)
                throw new AssertionError("Auxiliary mode must replace field, not amount");
            auxiliary.a(mode, -3, true);
            if(field.getInt(auxiliary)!=-3) throw new AssertionError("Signed auxiliary");
        }
        eZL modifier = new eZL();
        eVn definition = (eVn) Proxy.newProxyInstance(eVn.class.getClassLoader(),
            new Class<?>[] {eVn.class}, (proxy, method, values) -> {
                if (method.getName().equals("a")) return new int[] {1,25,0}[(int)values[0]];
                throw new UnsupportedOperationException(method.getName());
            });
        Field definitionField = Qe.class.getDeclaredField("bfp");
        definitionField.setAccessible(true);
        definitionField.set(modifier, definition);
        modifier.C(null);
        eXt source = new eXt();
        Field valueField = Qe.class.getDeclaredField("aSg");
        valueField.setAccessible(true);
        valueField.setInt(source,100);
        Method apply = eZL.class.getDeclaredMethod("c",Qe.class,boolean.class);
        apply.setAccessible(true);
        apply.invoke(modifier,source,false);
        if (source.getValue()!=125 || modifier.getValue()!=25 || !modifier.fNj())
            throw new AssertionError("eZL source mutation or own notification suppression");
        System.out.println("PASS 12 amount cases and original eZL mutation/suppression");
    }
}
