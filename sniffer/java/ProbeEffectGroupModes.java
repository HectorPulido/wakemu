import java.nio.file.Path;
import java.util.*;
import com.google.gson.Gson;

/** Offline native eYg.C/target-mode probe, without actors or a fight. */
public class ProbeEffectGroupModes {
    static class GroupAtLevel extends eYg {
        final short level;
        GroupAtLevel(short level) { this.level = level; }
        @Override public short fRR() { return level; }
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        // C requires an initialized manager to decode mode fields. Its group
        // lookup may be empty: this probe does not execute child effects.
        fyE.a(new fyE<fyD>() {});
        short level = Short.parseShort(args[0]);
        for (int arg = 1; arg < args.length; arg++) {
            int id = Integer.parseInt(args[arg]);
            eVn effect = bcA.dcX().AH(id);
            if (effect == null || effect.awM() != 330) throw new IllegalArgumentException("Not class330: " + id);
            GroupAtLevel group = new GroupAtLevel(level);
            group.bfp = effect;
            group.C(null);
            Map<String,Object> result = new LinkedHashMap<>();
            result.put("effect_id", id); result.put("level", level);
            List<Integer> parameters = new ArrayList<>();
            for (int i=0; i<effect.fKJ(); i++) parameters.add(effect.a(i,level,eVh.rpA));
            result.put("parameters",parameters);
            result.put("raw_target_parameter", effect.fKJ()>=3 ? effect.So(2) : null);
            result.put("on_target",group.bbA()); result.put("on_cell",group.bbB());
            result.put("transmit_target",group.fPT());
            for(String name:new String[]{"rEP","rFl","rFm","rFo"}) {
                var field=eYg.class.getDeclaredField(name);field.setAccessible(true);
                result.put(name,field.get(group));
            }
            System.out.println(new Gson().toJson(result));
        }
    }
}
