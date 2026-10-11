import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** Read the installed eZq/faB contract without constructing an invented actor. */
public class ProbeNative994Contract {
    public static void main(String[] args) throws Exception {
        eVj entry = eVi.ruv;
        if (entry.d() != 994 || entry.bkv().getClass() != eZq.class)
            throw new AssertionError("Runner identity");
        Method factory = eZq.class.getDeclaredMethod("fRo");
        factory.setAccessible(true);
        faB configuration = (faB) factory.invoke(entry.bkv());
        if (configuration.aXA() != 2349 || configuration.fSZ() != 4
            || configuration.fTa() || configuration.fTb() || configuration.fTf()
            || configuration.fTh() || configuration.fTe().getClass() != faD.class)
            throw new AssertionError("Native target-copy configuration");
        System.out.println("PASS994: runner=eZq, profile=2349, capacity=4, source=target, clone_spell_objects=false, self_control=false");
        System.out.println("excluded_root_classes=" + eVi.rur.d() + "," + eVi.rux.d());
        eHK template = new eHK();
        Method type = eHK.class.getDeclaredMethod("fxb");
        type.setAccessible(true);
        if (((Byte) type.invoke(template)) != 3)
            throw new AssertionError("Descriptor subtype");
        System.out.println("descriptor_subtype=3");
    }
}
