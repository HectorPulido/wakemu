import java.util.ArrayList;
import java.util.Arrays;
import java.util.Iterator;
import java.util.List;
import gnu.trove.map.hash.TLongObjectHashMap;

/** Offline proof of native ayT segment order and Trove value ordering. */
public final class ProbeNativeGlobalPVIterator {
    private static <T> List<T> consume(Iterator<T> iterator) {
        List<T> output = new ArrayList<>();
        while (iterator.hasNext()) {
            if (!iterator.hasNext()) throw new AssertionError("Repeated hasNext changed result");
            output.add(iterator.next());
        }
        return output;
    }

    public static void main(String[] args) {
        List<Long> fighters = Arrays.asList(9L, 2L);
        List<Long> areas = Arrays.asList(-4L, -1L);
        List<Long> extras = Arrays.asList(9L);
        List<Long> concatenated = consume(new ayT<Long>(Arrays.asList(
            fighters.iterator(), areas.iterator(), extras.iterator())));
        if (!concatenated.equals(Arrays.asList(9L, 2L, -4L, -1L, 9L))) {
            throw new AssertionError("Native ayT segment order: " + concatenated);
        }
        TLongObjectHashMap<Long> map = new TLongObjectHashMap<>();
        for (long identity : new long[]{9, 2, -4, -1, 8}) map.put(identity, identity);
        System.out.println("ayT=" + concatenated);
        System.out.println("Trove.values=" + map.valueCollection());
        map.remove(2);
        map.put(20, 20L);
        System.out.println("Trove.afterRemoveAndPut=" + map.valueCollection());
        System.out.println("PASS: native segment composition; no fighter/area filter claim");
    }
}
