import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/** Isolated client-policy unit fixture; no original-client semantics claimed. */
public class ProbeNativeSpellAvailability {
    public static void main(String[] args) {
        Fighter actor = new Fighter();
        Fight fight = new Fight(actor);
        aTx.player = new Player(fight);
        Shortcut shortcut = new Shortcut();
        check(NativeSpellAvailability.afterPreflight(fyJ.twJ, shortcut, "usable") == fyJ.twJ);
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        fight.summons = 1;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twD);
        fight.ap = 0;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        fight.ap = 4;
        actor.owned = false;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        actor.owned = true;
        fight.emptyOnly = true;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twD);
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "description") == fyJ.twV);

        // The helper must resolve this exact shortcut UID, not another spell in the book.
        check(fight.lastBookUid == shortcut.uid);
        shortcut.uid = 778;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        shortcut.uid = 777;

        // The complete native query remains the authority for cost and target rules.
        fight.summons = 1;
        fight.requiredAp = 5;
        fight.ap = 4;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        fight.ap = 5;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twD);
        fight.requiredAp = 0;
        fight.ownerAuthorized = false;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        fight.ownerAuthorized = true;

        // Missing authority and pathological bounds fail closed without scanning cells.
        fight.queryCount = 0;
        fight.qi.width = 20001;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        check(fight.queryCount == 1); // only the registered fighter PV was checked
        fight.qi.width = 2;
        fight.qi.available = false;
        fight.queryCount = 0;
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        check(fight.queryCount == 1);

        // The candidate walk is bounded by the map area, and an empty-cell hit
        // uses the native QI surface while duplicate PV coordinates are queried once.
        fight.qi.available = true;
        fight.qi.width = 100;
        fight.qi.height = 100;
        fight.qi.surface = 9;
        fight.castRange = 200;
        actor.cell = new aBn(0, 0, (short) 7);
        fight.targets.add(new FighterAt(new aBn(0, 0, (short) 7)));
        fight.targets.add(new FighterAt(new aBn(1, 0, (short) 7)));
        fight.emptyOnly = true;
        fight.emptyX = 1000;
        fight.queryCount = 0;
        fight.queriedCells.clear();
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twV);
        check(fight.queryCount == 10002 && fight.queriedCells.size() == 10002);
        fight.emptyX = 2;
        fight.queryCount = 0;
        fight.queriedCells.clear();
        check(NativeSpellAvailability.afterPreflight(fyJ.twV, shortcut, "usable") == fyJ.twD);
        check(fight.queryCount <= 10002);
        check(fight.queriedCells.contains("2:0:9"));

        System.out.println("NativeSpellAvailability policy: 21 assertions PASS");
    }
    static void check(boolean result) { if (!result) throw new AssertionError(); }
}
class CaptureAgent {
    static Object call(Object object, String name, Object... args) throws Exception {
        Class<?> type = object instanceof Class ? (Class<?>) object : object.getClass();
        for (Class<?> t = type; t != null; t = t.getSuperclass()) {
            for (Method method : t.getDeclaredMethods()) {
                if (method.getName().equals(name) && method.getParameterCount() == args.length) {
                    method.setAccessible(true);
                    try { return method.invoke(object instanceof Class ? null : object, args); }
                    catch (IllegalArgumentException mismatch) { }
                }
            }
        }
        throw new NoSuchMethodException(name);
    }
    static Object field(Object object, String name) throws Exception {
        var field = ((Class<?>) object).getDeclaredField(name);
        field.setAccessible(true);
        return field.get(null);
    }
}
class aTx {
    static Player player;
    static aTx cWt() { return new aTx(); }
    Player cWu() { return player; }
}
enum fyJ { twD, twV, twJ }
class Player {
    final Fight fight;
    Player(Fight fight) { this.fight = fight; }
    Fight doI() { return fight; }
}
class Shortcut { long uid = 777; long LV() { return uid; } }
class Fighter {
    boolean owned = true;
    aBn cell = new aBn(0, 0, (short) 7);
    aBn baM() { return cell; }
    boolean doz() { return owned; }
    Book js(long uid) { return uid == 777 ? new Book(uid) : null; }
    byte bcL() { return 0; }
}
class Book {
    final long uid;
    Book(long uid) { this.uid = uid; }
    Definition gtZ() { return new Definition(); }
}
class Definition { int i(Book book, Fighter actor, Object target, Object context) { return ((Fight) context).castRange; } }
class Timeline {
    final Fighter actor;
    Timeline(Fighter actor) { this.actor = actor; }
    Fighter dNG() { return actor; }
}
class FighterAt {
    final aBn cell;
    FighterAt(aBn cell) { this.cell = cell; }
    aBn baM() { return cell; }
}
class Fight {
    final Fighter actor;
    int summons = 0, ap = 4;
    int requiredAp, queryCount, emptyX = 1, castRange = 2;
    boolean emptyOnly, ownerAuthorized = true;
    long lastBookUid = -1;
    final QI qi = new QI();
    final List<FighterAt> targets = new ArrayList<>();
    final java.util.Set<String> queriedCells = new java.util.HashSet<>();
    Fight(Fighter actor) { this.actor = actor; targets.add(new FighterAt(actor.baM())); }
    Timeline dLW() { return new Timeline(actor); }
    List<FighterAt> dLy() { return targets; }
    QI bad() { return qi; }
    Object bbg() { return this; }
    fyJ a(Fighter caster, Book book, aBn cell, boolean check) {
        queryCount++;
        lastBookUid = book.uid;
        queriedCells.add(cell.getX() + ":" + cell.getY() + ":" + cell.bdn());
        queriedCells.add(cell.getX() + ":" + cell.getY() + ":" + cell.bdn());
        return summons > 0 && ap >= Math.max(1, requiredAp) && cell.bdn() == qi.surface &&
                (!emptyOnly || cell.getX() == emptyX) && ownerAuthorized && caster.owned ? fyJ.twD : fyJ.twV;
    }
}
class QI {
    int x, y, width = 2, height = 2;
    int surface = 7;
    boolean available = true;
    int bgq() { return x; }
    int bgr() { return y; }
    int getWidth() { return width; }
    int getHeight() { return height; }
    short X(int x, int y) { if (!available) throw new IllegalStateException("no QI"); return (short) surface; }
}
class aBn {
    final int x, y;
    final short z;
    public aBn(int x, int y, short z) { this.x = x; this.y = y; this.z = z; }
    int getX() { return x; }
    int getY() { return y; }
    short bdn() { return z; }
}
