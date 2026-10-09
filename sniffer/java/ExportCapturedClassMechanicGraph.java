import java.io.*;
import java.nio.file.*;
import java.util.*;

import com.google.gson.*;
/** Original typed closure from class2 captured books and native initial states only. */
public final class ExportCapturedClassMechanicGraph extends ExportClassMechanicGraph {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) throw new IllegalArgumentException("output-jsonl.gz scoped-profile-json...");
        profiles = new JsonObject();
        Set<Integer> seeds = new TreeSet<>();
        for (int index=1; index<args.length; index++) {
            JsonObject source = JsonParser.parseString(Files.readString(Path.of(args[index]))).getAsJsonObject();
            JsonObject records = source.getAsJsonObject("profiles");
            for (var entry : records.entrySet()) {
                if (profiles.has(entry.getKey()) && !profiles.get(entry.getKey()).equals(entry.getValue()))
                    throw new IllegalArgumentException("Conflicting original profile metadata");
                profiles.add(entry.getKey(), entry.getValue());
                seeds.add(Integer.parseInt(entry.getKey()));
            }
        }
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX record){GROUPS.put(record.d(),record.cku());}});
        apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw record){CRITERIA.put(record.aZE(),record.cyi());}});
        apw.bGL().a(new aNv(),new apB<aNv>(){public void load(aNv record){STATES.put(record.d(),snapshotRecord(record));}});
        apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa record){AREAS.put(record.d(),snapshotRecord(record));}});
        fyZ.guX().a(new bbV());
        Path target=Path.of(args[0]), temporary=target.resolveSibling(target.getFileName()+".tmp");
        try (BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new java.util.zip.GZIPOutputStream(Files.newOutputStream(temporary)),java.nio.charset.StandardCharsets.UTF_8))) {
            output=writer;
            for (int id:seeds) {
                enqueue("profile",id);
                JsonArray triples=profiles.getAsJsonObject(Integer.toString(id)).getAsJsonArray("initial_state_triples");
                for (int index=0;index<triples.size();index+=3)enqueue("state",triples.get(index).getAsInt());
            }
            while(!QUEUE.isEmpty()) {
                String key=QUEUE.removeFirst();if(!SEEN.add(key))continue;
                int split=key.indexOf(':');String kind=key.substring(0,split);int id=Integer.parseInt(key.substring(split+1));
                switch(kind) {case "spell"->spell(id);case "state"->state(id);case "area"->area(id);case "profile"->profile(id);case "effect"->effect(id);default->throw new IllegalStateException(key);}
            }
        }
        Files.move(temporary,target,StandardCopyOption.REPLACE_EXISTING);
        System.out.println("PASS captured typed closure "+COUNTS);
    }
}
