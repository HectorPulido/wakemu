import java.awt.EventQueue;
import java.lang.reflect.Field;
import java.util.Map;

/** Offline native-shape doubles; never loads or starts the game client. */
public final class OpenPlantingAgentRecoveryTest {
    static int checks;
    static void check(boolean condition, String message) {
        checks++;
        if (!condition) throw new AssertionError(message);
    }
    static Map<Object,Object> pending() throws Exception {
        Field field = OpenPlantingAgentRecovery.class.getDeclaredField("PENDING");
        field.setAccessible(true);
        return (Map<Object,Object>) field.get(null);
    }
    static void due(dev owner) throws Exception {
        Object value = pending().get(owner);
        Field changed = value.getClass().getDeclaredField("changed");
        changed.setAccessible(true);
        changed.setLong(value, 0L);
        Field position = value.getClass().getDeclaredField("position");
        position.setAccessible(true);
        position.set(value, aTx.INSTANCE.actor.graphic.position);
    }
    static dev setup() throws Exception {
        pending().clear();
        dev owner = new dev();
        owner.oaX = new Target(10, 20);
        aTx.INSTANCE.active = owner;
        aTx.INSTANCE.actor.movement = null;
        aTx.INSTANCE.actor.graphic.position = "0,0,0";
        OpenPlantingAgentRecovery.pending(owner, owner.oaX);
        return owner;
    }
    static void onEdt(Runnable action) throws Exception { EventQueue.invokeAndWait(action); }
    public static void main(String[] args) throws Exception {
        dev owner = setup();
        check(OpenPlantingAgentRecovery.waitingLimit(owner) == 498, "500 total cells by default");
        System.setProperty("wakfu.local.plantingQueueLimit", "750");
        check(OpenPlantingAgentRecovery.waitingLimit(owner) == 748, "configured total queue cap");
        check(OpenPlantingAgentRecovery.waitingLimit(new Object()) == 98, "other native actions unchanged");
        System.setProperty("wakfu.local.plantingQueueLimit", "1");
        check(OpenPlantingAgentRecovery.waitingLimit(owner) == 0, "lower clamp");
        System.setProperty("wakfu.local.plantingQueueLimit", "99999");
        check(OpenPlantingAgentRecovery.waitingLimit(owner) == 4998, "upper clamp");
        System.clearProperty("wakfu.local.plantingQueueLimit");
        check(!OpenPlantingAgentRecovery.beginRequest(owner, 11, 20), "stale destination cannot send");
        check(OpenPlantingAgentRecovery.beginRequest(owner, 10, 20), "first request accepted");
        check(!OpenPlantingAgentRecovery.beginRequest(owner, 10, 20), "request never sent twice");
        due(owner);
        onEdt(OpenPlantingAgentRecovery::recover);
        check(owner.retries == 0, "sent request never retried");
        owner.oaX = new Target(10, 20);
        OpenPlantingAgentRecovery.pending(owner, owner.oaX);
        check(OpenPlantingAgentRecovery.beginRequest(owner, 10, 20), "new target identity at same coordinates can send");
        aTx.INSTANCE.active = null;
        onEdt(OpenPlantingAgentRecovery::recover);
        check(!pending().containsKey(owner), "cancelled requested action is cleaned up");
        owner = setup();
        Callback stale = new Callback(owner), current = new Callback(owner);
        owner.nGo = current;
        check(!OpenPlantingAgentRecovery.acceptCallback(stale), "stale movement token rejected");
        check(OpenPlantingAgentRecovery.acceptCallback(current), "current movement token accepted");
        owner = setup();
        Target original = owner.oaX;
        owner.clearOnRetry = true;
        due(owner);
        onEdt(OpenPlantingAgentRecovery::recover);
        check(owner.retries == 1, "stalled unsent movement retried");
        check(owner.retryOnEdt, "retries execute on EDT");
        check(owner.oaX == original, "native path failure preserves selected target");
        owner = setup();
        owner.clearOnRetry = true;
        owner.cancelOnRetry = true;
        due(owner);
        onEdt(OpenPlantingAgentRecovery::recover);
        check(owner.oaX == null && !pending().containsKey(owner), "cancel during retry is not undone");
        owner = setup();
        OpenPlantingAgentRecovery.pending(owner, null);
        onEdt(OpenPlantingAgentRecovery::recover);
        check(owner.retries == 0 && pending().isEmpty(), "cancelled queue stays cancelled");
        owner = setup();
        due(owner);
        aTx.INSTANCE.active = null;
        onEdt(OpenPlantingAgentRecovery::recover);
        check(owner.retries == 0 && pending().isEmpty(), "inactive action is discarded");
        owner = setup();
        due(owner);
        aTx.INSTANCE.actor.movement = new Object();
        onEdt(OpenPlantingAgentRecovery::recover);
        check(owner.retries == 0, "active movement is not restarted");
        owner = setup();
        due(owner);
        aTx.INSTANCE.actor.graphic.position = "1,0,0";
        onEdt(OpenPlantingAgentRecovery::recover);
        check(owner.retries == 0, "movement progress refreshes recovery deadline");
        boolean rejected = false;
        try { OpenPlantingAgentRecovery.recover(); }
        catch (IllegalStateException expected) { rejected = true; }
        check(rejected, "off-EDT recovery rejected");
        pending().clear();
        System.out.println("PASS " + checks + " offline planting queue checks");
    }
}
class dev {
    Target oaX;
    Object nGo;
    int retries;
    boolean clearOnRetry, cancelOnRetry, retryOnEdt;
    void a(Target target) {
        retries++;
        retryOnEdt = EventQueue.isDispatchThread();
        if (clearOnRetry) oaX = null;
        if (cancelOnRetry) OpenPlantingAgentRecovery.pending(this, null);
    }
}
class Target {
    final int x, y;
    Target(int x, int y) { this.x = x; this.y = y; }
    int eXl() { return x; }
    int eXm() { return y; }
    String eVx() { return x + "," + y; }
}
class Callback {
    final dev obc;
    Callback(dev owner) { obc = owner; }
}
class aTx {
    static final aTx INSTANCE = new aTx();
    dev active;
    final Actor actor = new Actor();
    static aTx cWt() { return INSTANCE; }
    boolean c(Object owner) { return owner == active; }
    Actor cWu() { return actor; }
}
class Actor {
    Object movement;
    final Graphic graphic = new Graphic();
    Object dtg() { return movement; }
    Graphic dhw() { return graphic; }
}
class Graphic {
    String position = "0,0,0";
    String bqg() { return position; }
}
