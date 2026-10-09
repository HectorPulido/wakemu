import java.lang.reflect.*;
import java.util.*;
/** Original fan lists and real fff current-then-maximum setter oracle. */
public class ProbeNativeCapturedScaling {
    public static void main(String[] args) throws Exception {
        for (String name : new String[]{"rJJ", "rJK"}) {
            Field field = fan.class.getDeclaredField(name);
            field.setAccessible(true);
            List<ffw> group = (List<ffw>) field.get(fan.rJL);
            System.out.println(name + " " + group.stream().map(x -> Integer.toString(x.aKg())).toList());
        }
        Method scale = fan.class.getDeclaredMethod("a", ffw.class, float.class);
        scale.setAccessible(true);
        Field owner = fan.class.getDeclaredField("rJI");
        owner.setAccessible(true);
        for (float factor : new float[]{0, .5f, 1, 1.5f}) {
            fff pa = new fff(ffw.sgC, 0, 100);
            pa.or(100); pa.on(80);
            ffa source = (ffa) Proxy.newProxyInstance(ffa.class.getClassLoader(),
                new Class[]{ffa.class}, (p, method, a) -> {
                    if (method.getName().equals("b")) return pa;
                    throw new AssertionError(method);
                });
            owner.set(fan.rJL, source);
            scale.invoke(fan.rJL, ffw.sgC, factor);
            System.out.println(factor + " " + pa.aYS() + " " + pa.aYU() + " " + pa.aYV());
        }
        owner.set(fan.rJL, null);
    }
}
