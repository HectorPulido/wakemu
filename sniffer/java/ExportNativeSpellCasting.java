import java.nio.file.*;import java.io.*;import java.util.*;import java.lang.reflect.*;import java.util.zip.*;import com.google.gson.Gson;
/** Offline all installed aNr casting metadata. Stream JSON; no client connection. */
public class ExportNativeSpellCasting {
 public static void main(String[]args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(), new apB<aKX>(){public void load(aKX raw){}});
  apw.bGL().a(new aNw(), new apB<aNw>(){public void load(aNw raw){}});
  Field base=fyF.class.getDeclaredField("twf");base.setAccessible(true);
  Field categories=fyF.class.getDeclaredField("rgG");categories.setAccessible(true);
  Field categoryID=fyU.class.getDeclaredField("tye");categoryID.setAccessible(true);
  Method conditional=bPS.class.getDeclaredMethod("a",aNs.class);conditional.setAccessible(true);
  Gson gson=new Gson();int[]count={0};
  try(Writer out=new BufferedWriter(new OutputStreamWriter(Files.newOutputStream(Path.of(args[0])),java.nio.charset.StandardCharsets.UTF_8))){
   out.write("{\"source\":\"Installed aNr/bPS/fyF/fyP casting and conditional tables, offline\",\"spells\":{");
   apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr raw){try{
    bPK spell=bPS.elL().IP(raw.d());fyP table=(fyP)base.get(spell);Map<String,Object>record=new LinkedHashMap<>();
    record.put("range_modifiable",table.guk());record.put("protected",spell.elO());record.put("maximum_level",spell.Fq());record.put("line_of_sight",table.cwL());record.put("linear",table.cwM());record.put("free_cell",table.cwU());record.put("path_option",table.cwN());record.put("diagonal",table.cwT());record.put("linear_path",table.cwV());record.put("allow_self",table.cwE());record.put("forbid_QI_P",spell.gjl());record.put("cast_criterion_raw",raw.cwd());record.put("cast_criterion_native_present",spell.gtP()!=null);
    List<Object>levels=new ArrayList<>(),costs=new ArrayList<>();
    for(short l=1;l<=spell.Fq();l++){List<Integer>roots=new ArrayList<>();Iterator<eVn>it=spell.fG(l);while(it.hasNext())roots.add(it.next().aZE());levels.add(List.of(table.gui().Qi(l),table.guj().Qi(l),roots));costs.add(List.of(spell.aai(l),spell.aal(l),spell.aaj(l)));}
    record.put("levels",levels);record.put("costs",costs);
    Set<Integer>cat=new TreeSet<>();Object enumset=categories.get(spell);if(enumset!=null)for(Object value:(Set<?>)enumset)cat.add(categoryID.getInt(value));record.put("categories",cat);
    List<Object>rules=new ArrayList<>();for(var entry:raw.cwI().entrySet()){
     fyP alternate=(fyP)conditional.invoke(null,entry.getValue());List<Object>values=new ArrayList<>(),ranges=new ArrayList<>();
     for(short l=1;l<=spell.Fq();l++){values.add(List.of(alternate.c(ffw.sgD,l),alternate.c(ffw.sgE,l),alternate.c(ffw.sgF,l)));ranges.add(List.of(alternate.gui().Qi(l),alternate.guj().Qi(l)));}
     Map<String,Object>rule=new LinkedHashMap<>();rule.put("criteria",entry.getKey());rule.put("levels",values);rule.put("ranges",ranges);rule.put("line_of_sight",alternate.cwL());rule.put("linear",alternate.cwM());rule.put("free_cell",alternate.cwU());rule.put("path_option",alternate.cwN());rule.put("diagonal",alternate.cwT());rule.put("linear_path",alternate.cwV());rule.put("allow_self",alternate.cwE());rule.put("range_modifiable",alternate.guk());rules.add(rule);
    }record.put("conditional",rules);
    if(count[0]++>0)out.write(",");out.write(gson.toJson(Integer.toString(raw.d()))+":"+gson.toJson(record));
   }catch(Exception error){throw new RuntimeException("spell "+raw.d(),error);}}});out.write("}}\n");
  }System.out.println("Exported "+count[0]+" installed native casting definitions");
 }
}
