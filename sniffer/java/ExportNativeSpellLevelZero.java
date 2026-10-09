import java.nio.file.*;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.*;
import com.google.gson.Gson;

/** Offline native fG(0) roots and parameter evidence; explicit input references. */
public class ExportNativeSpellLevelZero {
    static Map<Integer,int[]> groups = new HashMap<>();
    static SortedMap<String,Object> effects = new TreeMap<>();
    static Map<String,Object> flags(fyP table) {
        Map<String,Object> value = new LinkedHashMap<>();
        value.put("line_of_sight",table.cwL()); value.put("linear",table.cwM());
        value.put("free_cell",table.cwU()); value.put("path_option",table.cwN());
        value.put("diagonal",table.cwT()); value.put("linear_path",table.cwV());
        value.put("allow_self",table.cwE()); value.put("range_modifiable",table.guk());
        return value;
    }
    static void visit(int reference) {
        String key = Integer.toString(reference);
        if (effects.containsKey(key)) return;
        eVn effect = bcA.dcX().AH(reference);
        if (effect == null) throw new IllegalStateException("Missing native zero-level effect " + reference);
        int[] children = groups.getOrDefault(reference, new int[0]);
        List<Integer> parameters = new ArrayList<>();
        for (int index=0; index<effect.fKJ(); index++) parameters.add(effect.a(index,(short)0,eVh.rpA));
        effects.put(key, Map.of("family",effect.awM(),"children",children,
            "minimum_level",effect.fKR(),"maximum_level",effect.fKS(),
            "parameters",parameters,"probability",effect.eg((short)0)));
        for (int child : children) visit(child);
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(),new apB<aKX>() { public void load(aKX group) { groups.put(group.d(),group.cku()); }});
        Field base = fyF.class.getDeclaredField("twf"); base.setAccessible(true);
        Field rawManager = bPS.class.getDeclaredField("kMi"); rawManager.setAccessible(true);
        Field categories = fyF.class.getDeclaredField("rgG"); categories.setAccessible(true);
        Field categoryID = fyU.class.getDeclaredField("tye"); categoryID.setAccessible(true);
        Method conditional = bPS.class.getDeclaredMethod("a",aNs.class); conditional.setAccessible(true);
        SortedMap<String,Object> spells = new TreeMap<>();
        SortedMap<String,Object> casting = new TreeMap<>();
        for (String text : Files.readAllLines(Path.of(args[0]))) {
            int reference = Integer.parseInt(text); bPK spell = bPS.elL().IP(reference);
            if (spell == null) throw new IllegalStateException("Missing native spell " + reference);
            fyP table = (fyP)base.get(spell); List<Integer> roots = new ArrayList<>();
            Iterator<eVn> iterator = spell.fG((short)0);
            while(iterator.hasNext()) { int effect=iterator.next().aZE(); roots.add(effect); visit(effect); }
            spells.put(text, List.of(table.gui().Qi(0),table.guj().Qi(0),roots));
            Map<String,Object> record = new LinkedHashMap<>();
            record.put("levels",List.of(List.of(table.gui().Qi(0),table.guj().Qi(0),roots)));
            record.put("costs",List.of(List.of(spell.aai(0),spell.aal(0),spell.aaj(0))));
            record.putAll(flags(table));
            SortedSet<Integer> categoryIds = new TreeSet<>();
            Object enumset = categories.get(spell);
            if(enumset != null) for(Object value:(Set<?>)enumset) categoryIds.add(categoryID.getInt(value));
            record.put("categories",categoryIds);
            aNr raw = (aNr)((apy<?>)rawManager.get(bPS.elL())).tD(reference);
            record.put("forbid_QI_P",spell.gjl());
            record.put("cast_criterion_raw",raw.cwd());
            record.put("cast_criterion_native_present",spell.gtP()!=null);
            List<Object> rules = new ArrayList<>();
            for(var entry:raw.cwI().entrySet()) {
                fyP alternate = (fyP)conditional.invoke(null,entry.getValue());
                Map<String,Object> rule = new LinkedHashMap<>(flags(alternate));
                rule.put("criteria",entry.getKey());
                rule.put("levels",List.of(List.of(alternate.c(ffw.sgD,(short)0),alternate.c(ffw.sgE,(short)0),alternate.c(ffw.sgF,(short)0))));
                rule.put("ranges",List.of(List.of(alternate.gui().Qi(0),alternate.guj().Qi(0))));
                rules.add(rule);
            }
            record.put("conditional",rules); casting.put(text,record);
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(Map.of("schema",1,
            "source","Installed bPS/fyF.fG(short0), fyP.Qi0 and eVE parameter/probability0; offline",
            "spells",spells,"casting",casting,"effects",effects)));
        System.out.println("Exported native zero-level spell roots="+spells.size()+" effect closure="+effects.size());
    }
}
