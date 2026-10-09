import java.io.*;
import com.google.gson.*;

/** Native Sm/VA physical transition oracle; stdin JSON, no client or network. */
public class ProbeNativeSmTransitions {
    static Vy[] column(JsonArray rows) {
        Vy[] result = new Vy[rows.size()];
        for (int i = 0; i < result.length; i++) {
            JsonArray row = rows.get(i).getAsJsonArray();
            Vy v = new Vy();
            v.bbl = row.get(0).getAsShort(); v.bLD = row.get(1).getAsByte();
            v.bLE = row.get(2).getAsByte(); v.bLF = row.get(3).getAsShort();
            v.aYX = row.get(4).getAsByte(); v.bLf = row.get(5).getAsBoolean();
            result[i] = v;
        }
        return result;
    }
    public static void main(String[] args) throws Exception {
        BufferedReader input = new BufferedReader(new InputStreamReader(System.in));
        String line;
        while ((line = input.readLine()) != null) {
            JsonObject request = JsonParser.parseString(line).getAsJsonObject();
            Vy[] start = column(request.getAsJsonArray("start"));
            Vy[] end = column(request.getAsJsonArray("end"));
            Sm sm = new Sm(request.get("height").getAsInt(), (byte)0,
                           request.get("jump").getAsInt(), true);
            JsonObject output = new JsonObject();
            try {
                int count = sm.a(request.get("index").getAsInt(), 0, start.length,
                                start, 0, end.length, end);
                JsonArray indices = new JsonArray();
                for (int i = 0; i < count; i++) indices.add(sm.boE[i]);
                output.add("indices", indices);
            } catch (Throwable error) {
                output.addProperty("error", error.getClass().getName());
            }
            System.out.println(output);
        }
    }
}
