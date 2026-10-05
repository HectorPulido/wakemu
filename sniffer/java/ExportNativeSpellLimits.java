import java.nio.file.*;import java.util.*;import java.lang.reflect.*;import com.google.gson.Gson;
/** Native fyP limits; conditional tables retained without guessing conditions. */
public class ExportNativeSpellLimits {
 static List<Integer> values(fyP t){return List.of((int)(byte)(int)t.cwQ(),(int)(byte)(int)t.cwR(),(int)(byte)(int)t.cwS(),(int)(byte)(int)t.cwP());}
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Field base=fyF.class.getDeclaredField("twf");base.setAccessible(true);Method alternative=bPS.class.getDeclaredMethod("a",aNs.class);alternative.setAccessible(true);
  Map<String,Object> spells=new TreeMap<>();
  apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr raw){try{
   bPK spell=bPS.elL().IP(raw.d());fyP table=(fyP)base.get(spell);List<Object>conditional=new ArrayList<>();
   for(var rule:raw.cwI().entrySet())conditional.add(Map.of("criteria",rule.getKey(),"limits",values((fyP)alternative.invoke(null,rule.getValue()))));
   spells.put(Integer.toString(raw.d()),Map.of("maximum_level",spell.Fq(),"limits",values(table),"conditional",conditional));
  }catch(Exception e){throw new RuntimeException("Spell "+raw.d(),e);}}});
  Path out=Path.of(args[0]),temp=out.resolveSibling(out.getFileName()+".tmp");Files.writeString(temp,new Gson().toJson(Map.of("schema",1,"source","Installed aNr/bPS/fyF/fyP; fyS usage gates and byte narrowing; offline","spells",spells)));Files.move(temp,out,StandardCopyOption.REPLACE_EXISTING);
  System.out.println("Exported "+spells.size()+" spell limits; Juicio="+spells.get("4776"));
 }
}
