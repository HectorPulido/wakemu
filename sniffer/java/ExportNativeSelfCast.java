import java.nio.file.*;import java.io.*;import java.util.*;import java.lang.reflect.*;import com.google.gson.Gson;
/** fyP.cwE self-target exception, offline installed spell population. */
public class ExportNativeSelfCast {
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX raw){}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){}});
  Field base=fyF.class.getDeclaredField("twf");base.setAccessible(true);
  Method alternate=bPS.class.getDeclaredMethod("a",aNs.class);alternate.setAccessible(true);
  Map<String,Object> rows=new TreeMap<>();
  apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr raw){try{
   bPK spell=bPS.elL().IP(raw.d());fyP table=(fyP)base.get(spell);List<Object>rules=new ArrayList<>();
   for(var entry:raw.cwI().entrySet())rules.add(Map.of("criteria",entry.getKey(),"allowed",((fyP)alternate.invoke(null,entry.getValue())).cwE()));
   rows.put(Integer.toString(raw.d()),Map.of("allowed",table.cwE(),"conditional",rules));
  }catch(Exception e){throw new RuntimeException(e);}}});
  Files.writeString(Path.of(args[0]),new Gson().toJson(Map.of("source","bPO.isCastableOnCaster -> fyF.l -> conditional fyP.cwE; fcj.a distance0 exception", "spells",rows))+"\n");
  System.out.println("Exported "+rows.size()+" self-cast policies; 6065="+new Gson().toJson(rows.get("6065")));
 }
}
