import java.nio.file.*;import java.lang.reflect.*;import java.util.*;import com.google.gson.GsonBuilder;
/** All installed definitions of selected families; counts are not reachable spell coverage. */
public final class AuditNativeObservationGuards {
 public static void main(String[] args)throws Exception{
  Set<Integer> selected=Set.of(20,31,41,191,56,57,192,193,986,1013,1201,1202,330,341,352,1103,400,402,877,649,1065);
  Map<Integer,Qe> prototypes=new TreeMap<>();for(Field f:eVi.class.getDeclaredFields())if(f.getType()==eVj.class&&Modifier.isStatic(f.getModifiers())){f.setAccessible(true);eVj r=(eVj)f.get(null);if(selected.contains(r.d()))prototypes.put(r.d(),(Qe)r.bkv());}
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Map<Integer,List<Integer>> refs=new TreeMap<>();apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){if(selected.contains(raw.awM()))refs.computeIfAbsent(raw.awM(),k->new ArrayList<>()).add(raw.aZE());}});
  Field pk=Qe.class.getDeclaredField("bfp");pk.setAccessible(true);List<Object> rows=new ArrayList<>();
  for(var family:prototypes.entrySet()){
   Qe runner=family.getValue();int yes=0,no=0;List<Integer> ys=new ArrayList<>(),ns=new ArrayList<>();
   for(int id:refs.getOrDefault(family.getKey(),List.of())){eVn definition=bcA.dcX().AH(id);pk.set(runner,definition);boolean value=runner.aZN();if(value){yes++;if(ys.size()<8)ys.add(id);}else{no++;if(ns.size()<8)ns.add(id);}}
   Map<String,Object> row=new LinkedHashMap<>();row.put("effect_class",family.getKey());row.put("runner",runner.getClass().getName());row.put("aZN_true_definitions",yes);row.put("aZN_false_definitions",no);row.put("true_examples",ys);row.put("false_examples",ns);rows.add(row);
  }
  Map<String,Object> out=new LinkedHashMap<>();out.put("scope","All installed definitions including legacy/unreachable; aZN only, not Ty/bbW/client delivery proof");out.put("families",rows);Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(out));System.out.println("Audited "+rows.size()+" native family guard populations");
 }
}
