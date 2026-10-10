import java.io.*;
import java.lang.reflect.Proxy;
import java.util.*;
import com.google.gson.*;

/** Original faz/Sm square-footprint traversal over explicit native Vy columns. */
public class ProbeNativeForcedFootprint {
    static class Grid extends ProbeNativeSnPath.Grid {
        final Set<String> blocked = new HashSet<>();
        final List<String> visits = new ArrayList<>();
        Grid(ProbeNativeSnPath.ColumnMap map, JsonArray rows) {
            super(map, new JsonArray());
            for (JsonElement row : rows) {
                JsonArray cell = row.getAsJsonArray();
                blocked.add(cell.get(0).getAsInt()+","+cell.get(1).getAsInt());
            }
        }
        public boolean g(int x, int y, short z) {
            visits.add(x+","+y+","+z);
            return false;
        }
        public boolean R(int x, int y) { return !blocked.contains(x+","+y); }
    }
    public static void main(String[] args) throws Exception {
        BufferedReader input = new BufferedReader(new InputStreamReader(System.in));
        String line;
        while ((line = input.readLine()) != null) {
            JsonObject request = JsonParser.parseString(line).getAsJsonObject();
            ProbeNativeSnPath.ColumnMap map = new ProbeNativeSnPath.ColumnMap();
            for (JsonElement entry : request.getAsJsonArray("columns")) {
                JsonArray row = entry.getAsJsonArray();
                map.rows.put(row.get(0).getAsInt()+","+row.get(1).getAsInt(),
                    ProbeNativeSmTransitions.column(row.get(2).getAsJsonArray()));
            }
            Grid grid = new Grid(map, request.getAsJsonArray("blocked"));
            JsonArray source = request.getAsJsonArray("source");
            fax actor = (fax)Proxy.newProxyInstance(fax.class.getClassLoader(),
                new Class<?>[]{fax.class}, (proxy, method, values) -> {
                    return switch(method.getName()) {
                        case "bcz" -> source.get(0).getAsInt();
                        case "bcA" -> source.get(1).getAsInt();
                        case "bcB" -> source.get(2).getAsShort();
                        case "bcK" -> request.get("height").getAsByte();
                        case "bcL" -> request.get("radius").getAsByte();
                        case "bvz" -> (short)4;
                        case "bcP" -> true;
                        default -> throw new AssertionError("Unexpected fax read "+method);
                    };
                });
            PN context = (PN)Proxy.newProxyInstance(PN.class.getClassLoader(),
                new Class<?>[]{PN.class}, (proxy, method, values) -> {
                    if (method.getName().equals("bad")) return grid;
                    throw new AssertionError("Unexpected PN read "+method);
                });
            JsonArray destination = request.getAsJsonArray("destination");
            faz computer = new faz(actor,
                new aBn(destination.get(0).getAsInt(),destination.get(1).getAsInt(),source.get(2).getAsShort()),
                1, context);
            fay result = computer.fSU();
            JsonObject output = new JsonObject();
            output.addProperty("collision", result.fSO());
            aBn point = result.fPe();
            JsonArray cell = new JsonArray();
            if (point != null) {
                cell.add(point.getX());cell.add(point.getY());cell.add(point.bdn());
            }
            output.add("destination", point == null ? JsonNull.INSTANCE : cell);
            output.add("visits",new Gson().toJsonTree(grid.visits));
            System.out.println(output);
        }
    }
}
