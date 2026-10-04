import java.util.*;
import java.util.zip.*;

/** Offline installed-map geometry; never contacts a game service. */
public class ExportCombatArena {
    static record Column(Vy[] surfaces, int count) {}
    static Column column(List<VB> chunks, int x, int y) {
        for (VB chunk : chunks) {
            if (x < chunk.bbn || x >= chunk.bbn + 18 || y < chunk.bbo || y >= chunk.bbo + 18) continue;
            Vy[] surfaces = Vy.blX();
            return new Column(surfaces, chunk.a(x, y, surfaces, 0));
        }
        return new Column(Vy.blX(), 0);
    }
    public static void main(String[] args) throws Exception {
        int map = Integer.parseInt(args[0]);
        int xmin = Integer.parseInt(args[1]), ymin = Integer.parseInt(args[2]);
        int xmax = Integer.parseInt(args[3]), ymax = Integer.parseInt(args[4]);
        List<VB> chunks = new ArrayList<>();
        try (ZipFile archive = new ZipFile("client/contents/maps/tplg/" + map + ".jar")) {
            for (var entry : Collections.list(archive.entries())) {
                if (!entry.getName().matches("-?\\d+_-?\\d+")) continue;
                aoG reader = aoG.dx(archive.getInputStream(entry).readAllBytes());
                VB chunk = VC.ag(reader.aJn());
                chunk.a(reader);
                chunks.add(chunk);
            }
        }
        List<String> cells = new ArrayList<>();
        for (int y = ymin; y <= ymax; y++) for (int x = xmin; x <= xmax; x++) {
            for (VB chunk : chunks) {
                if (x < chunk.bbn || x >= chunk.bbn + 18 || y < chunk.bbo || y >= chunk.bbo + 18) continue;
                Vy[] candidates = Vy.blX();
                int count = chunk.a(x, y, candidates, 0);
                // Keep all walkable surfaces. Arena construction must choose one
                // altitude per XY and validate movement edges separately.
                for (int i = 0; i < count; i++) if (candidates[i].bLD >= 0)
                    cells.add("[" + x + "," + y + "," + candidates[i].bbl + "]");
                break;
            }
        }
        List<String> edges = new ArrayList<>();
        for (int y = ymin; y <= ymax; y++) for (int x = xmin; x <= xmax; x++) {
            Column from = column(chunks, x, y);
            for (int[] delta : new int[][]{{1,0},{-1,0},{0,1},{0,-1}}) {
                int nx=x+delta[0], ny=y+delta[1];
                if (nx<xmin || nx>xmax || ny<ymin || ny>ymax) continue;
                Column to = column(chunks, nx, ny);
                for (int i=0; i<from.count; i++) {
                    if (from.surfaces[i].bLD<0) continue;
                    Sm movement = new Sm(3, (byte)0, 2, true);
                    int count = movement.a(i, 0, from.count, from.surfaces, 0, to.count, to.surfaces);
                    for (int j=0; j<count; j++) {
                        Vy target=to.surfaces[movement.boE[j]];
                        edges.add("[["+x+","+y+","+from.surfaces[i].bbl+"],["+nx+","+ny+","+target.bbl+"]]");
                    }
                }
            }
        }
        System.out.println("{\"map_id\":" + map + ",\"cells\":[" + String.join(",", cells)
            + "],\"edges\":[" + String.join(",", edges) + "]}");
    }
}
