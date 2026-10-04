import java.nio.file.*;import java.util.*;import com.google.gson.Gson;
public class ExportItemEquipmentConditions {public static void main(String[]args)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");Map<Integer,Map<String,String>> rows=new TreeMap<>();
 apw.bGL().a(new aLO(),new apB<aLO>(){public void load(aLO r){bJp item=new bIJ().f(r);if(item.dLn()==null)return;boolean supported=false;for(fnO slot:fnO.values())if(item.dLn().v(slot))supported=true;if(!supported)return;
 Map<String,String> cond=new TreeMap<>();String[]raw=r.cpz();if(raw!=null)for(int i=0;i+1<raw.length;i+=2){fnE kind=fnE.valueOf(raw[i]);if(item.a(kind)!=null)cond.put(kind.name(),raw[i+1]);}rows.put(r.d(),cond);}});
 Map<String,Object> result=new LinkedHashMap<>();result.put("source","Installed aLO.cpz -> bIJ.k -> fpC.a(fnE); raw native condition strings by equipment reference/action");result.put("items",rows);Files.writeString(Path.of(args[0]),new Gson().toJson(result));System.out.println("Exported "+rows.size()+" equipment references");
}}
