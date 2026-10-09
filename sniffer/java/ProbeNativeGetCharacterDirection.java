import java.lang.reflect.Field;
import java.util.ArrayList;

/** Offline probe for the native eJv GetCharacterDirection criterion. */
public final class ProbeNativeGetCharacterDirection {
    static final class FacingActor extends ProbeNativeLevelGroup.Actor {
        private final aAS facing;

        FacingActor(aAS facing) {
            this.facing = facing;
        }

        @Override
        public aAS bcy() {
            return facing;
        }
    }

    private static eJv criterion(String... arguments) {
        ArrayList<alS> parsed = new ArrayList<>();
        for (String argument : arguments) parsed.add(new amc(argument));
        return new eJv(parsed);
    }

    private static long evaluate(eJv criterion, Object caster, Object target) {
        return criterion.d(caster, target, null, null);
    }

    public static void main(String[] args) throws Exception {
        Field unsafeField = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        unsafeField.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) unsafeField.get(null);

        for (aAS facing : aAS.values()) {
            FacingActor caster = new FacingActor(facing);
            FacingActor target = new FacingActor(aAS.wL((facing.dyI + 1) % 8));
            System.out.println("enum=" + facing + ",dyI=" + facing.dyI
                    + ",noarg=" + evaluate(criterion(), caster, target)
                    + ",target=" + evaluate(criterion("target"), caster, target)
                    + ",target_case=" + evaluate(criterion("TaRgEt"), caster, target)
                    + ",other=" + evaluate(criterion("castercontroller"), caster, target));
        }

        FacingActor caster = new FacingActor(aAS.wL(2));
        FacingActor nullFacing = new FacingActor(null);
        System.out.println("null_facing=" + evaluate(criterion(), caster, nullFacing));
        System.out.println("null_target_selected=" + evaluate(criterion("target"), caster, null));
        System.out.println("unrecognized_actor_selected=" + evaluate(criterion("nobody"), null, null));
    }
}
