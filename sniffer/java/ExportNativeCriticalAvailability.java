import java.nio.file.*;import java.io.*;import java.util.*;import java.util.zip.*;import com.google.gson.Gson;
/** Original bPO.hasCriticalEffect root predicate eVn.dd(1L), all installed spells. */
public class ExportNativeCriticalAvailability {
 public static void main(String[]args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX r){}});
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw r){}});
  Map<String,Object>rows=new TreeMap<>();
  apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr raw){
   bPK spell=bPS.elL().IP(raw.d());List<Integer>allowed=new ArrayList<>();
   for(short level=1;level<=200;level++){
    Iterator<eVn>it=spell.fG((short)Math.min(level,spell.Fq()));boolean present=false;
    while(it.hasNext())if(it.next().dd(1L)){present=true;break;}
    if(present)allowed.add((int)level);
   }
   rows.put(Integer.toString(raw.d()),Map.of("maximum_level",spell.Fq(),"critical_levels",allowed));
  }});
  Map<String,Object>out=Map.of("source","Original bPO.eH(hasCriticalEffect): fyG.iterator -> fyF.fG(cmZ) -> any eVn.dd(1L); evaluated levels1..200, native max level clamp", "spells",rows);
  Files.writeString(Path.of(args[0]),new Gson().toJson(out)+"\n");
  for(int id:new int[]{6908,2043,5030,7225}){
   bPK spell=bPS.elL().IP(id); bPO value=new bPO(spell,(short)20,id,null);
   boolean actual=(Boolean)value.eH("hasCriticalEffect");
   Map record=(Map)rows.get(Integer.toString(id));boolean expected=((List)record.get("critical_levels")).contains(20);
   if(actual!=expected)throw new AssertionError("UI mismatch "+id+":"+actual+"/"+expected);
   System.out.println("PASS UI original availability "+id+"="+actual);
  }
  System.out.println("Exported "+rows.size()+" native spells");
 }
}
