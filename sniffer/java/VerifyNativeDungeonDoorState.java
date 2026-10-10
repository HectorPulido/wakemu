import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;

/** Verify prepared physical-door state packets with the installed client decoder. */
public class VerifyNativeDungeonDoorState {
    static class View extends bEy {
        boolean lastVisible = true;
        public void setVisible(boolean visible) { lastVisible = visible; }
        public void aPY() { }
        public void aF(boolean value) { }
    }
    static Object field(Object object, String name) throws Exception {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try { Field f = type.getDeclaredField(name); f.setAccessible(true); return f.get(object); }
            catch (NoSuchFieldException missing) { }
        }
        throw new NoSuchFieldException(name);
    }
    public static void main(String[] args) throws Exception {
        JsonArray input = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
        JsonObject baseline = null;
        for (JsonElement e : input) if (e.getAsJsonObject().get("id").getAsInt() == 26874) baseline = e.getAsJsonObject();
        if (baseline == null) throw new IllegalStateException("Missing native Tofu gate");
        for (int state : List.of(0, 1)) {
            bEG object = bEE.valueOf("Door").bej().bau();
            object.as(HexFormat.of().parseHex(baseline.get("payload_hex").getAsString()));
            Field unsafeField = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
            unsafeField.setAccessible(true);
            sun.misc.Unsafe unsafe = (sun.misc.Unsafe) unsafeField.get(null);
            View view = (View) unsafe.allocateInstance(View.class);
            view.lastVisible = true;
            @SuppressWarnings("unchecked")
            Collection<Nk> views = (Collection<Nk>) field(object, "aZd");
            views.add(view);
            String partial = "01020000000602" + (state == 0 ? "0000" : "0001") + (state == 0 ? "00000000000000000000" : "01000000000000000000");
            object.as(HexFormat.of().parseHex(partial));
            if (((Short) field(object, "bkP")) != state || object.isVisible() != (state == 1) || object.isUsable())
                throw new IllegalStateException("Native physical gate state mismatch");
            Method refresh = object.getClass().getDeclaredMethod("dfi");
            refresh.setAccessible(true);
            refresh.invoke(object);
            if (view.lastVisible != (state == 1))
                throw new IllegalStateException("Loaded native view visibility was not updated");
            boolean blocked = object.beu();
            if (blocked != (state == 1)) throw new IllegalStateException("Native gate collision mismatch");
            System.out.println("state=" + state + " visible=" + object.isVisible() + " usable=" + object.isUsable() + " blocked=" + blocked);
        }
    }
}
