/** Offline fresh eGj physical-position and jump source verification. */
public class ProbeNativeActorPhysics {
    public static void main(String[] args) throws Throwable {
        bjo actor = new bjo();
        var setter = java.lang.invoke.MethodHandles.privateLookupIn(
            eGj.class, java.lang.invoke.MethodHandles.lookup()).findSpecial(
                eGj.class, "a", java.lang.invoke.MethodType.methodType(
                    void.class, int.class, int.class, short.class), eGj.class).bindTo(actor);
        setter.invokeExact(7, -3, (short) 2);
        aBn physical = actor.efR();
        aBn logical = actor.baM();
        if (actor.bvz() != 4 || physical.getX() != 7 || physical.getY() != -3
                || physical.bdn() != 2 || logical == physical
                || logical.getX() != 7 || logical.getY() != -3 || logical.bdn() != 2)
            throw new AssertionError("Fresh eGj pGF and bvz");
        setter.invokeExact(-9, 4, (short) 1);
        if (actor.efR() != physical || physical.getX() != -9
                || physical.getY() != 4 || physical.bdn() != 1
                || logical.getX() != 7)
            throw new AssertionError("Actual pGF update versus baM copy");
        for (Class<?> type : new Class<?>[]{big.class, bjo.class, bje.class}) {
            if (type.getMethod("bvz").getDeclaringClass() != eGj.class
                    || type.getMethod("baM").getDeclaringClass() != eGj.class)
                throw new AssertionError("Unexpected native creation override");
        }
        System.out.println("PASS eGj efR pGF, baM copy, coordinate mutation, bvz4 inherited by big/bjo/bje");
    }
}
