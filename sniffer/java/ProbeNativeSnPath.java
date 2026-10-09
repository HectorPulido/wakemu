import java.io.*;
import java.util.*;
import com.google.gson.*;

/** Original Sn.a against explicit native VB/Vy and QI, without a game client. */
public class ProbeNativeSnPath {
    static class ColumnMap extends VB {
        final Map<String,Vy[]> rows = new HashMap<>();
        public boolean aI(int x, int y) { return true; }
        public short aL(int x, int y) { return 0; }
        public int a(int x, int y, Vz[] target, int offset) { return 0; }
        public int a(int x, int y, Vy[] target, int offset) {
            Vy[] column = rows.getOrDefault(x+","+y, new Vy[0]);
            for (int i=0;i<column.length;i++) target[offset+i].d(column[i]);
            return column.length;
        }
    }
    static class Grid extends QI {
        final ColumnMap map;
        Grid(ColumnMap value, JsonArray masks) {
            map=value; bpZ=0; bqa=0; bqd=18; bqe=18; biE=324; biD=new short[324];
            for (JsonElement row: masks) {
                JsonArray r=row.getAsJsonArray();
                biD[r.get(1).getAsInt()*18+r.get(0).getAsInt()] = r.get(2).getAsShort();
            }
        }
        public VB aO(int x,int y) { return map.aK(x,y) ? map : null; }
    }
    static class Path extends Sn { Path() { super(); } }
    static aBn point(JsonArray a) {
        return a == null ? null : new aBn(a.get(0).getAsInt(), a.get(1).getAsInt(), a.get(2).getAsShort());
    }
    public static void main(String[] args) throws Exception {
        BufferedReader reader=new BufferedReader(new InputStreamReader(System.in)); String line;
        Path sn=new Path();
        while ((line=reader.readLine())!=null) {
            JsonObject request=JsonParser.parseString(line).getAsJsonObject();
            ColumnMap map=new ColumnMap();
            for (JsonElement entry:request.getAsJsonArray("columns")) {
                JsonArray row=entry.getAsJsonArray();
                map.rows.put(row.get(0).getAsInt()+","+row.get(1).getAsInt(),
                             ProbeNativeSmTransitions.column(row.get(2).getAsJsonArray()));
            }
            Grid grid=new Grid(map,request.getAsJsonArray("masks"));
            sn.b(grid); sn.a(request.get("height").getAsInt(), request.get("radius").getAsByte(), request.get("jump").getAsShort());
            JsonObject output=new JsonObject();
            try { output.addProperty("result",sn.a(point(request.getAsJsonArray("source")), point(request.getAsJsonArray("target")),request.get("path_option").getAsBoolean())); }
            catch(Throwable error) { output.addProperty("error",error.getClass().getName()); }
            finally { sn.bal(); }
            System.out.println(output);
        }
    }
}
