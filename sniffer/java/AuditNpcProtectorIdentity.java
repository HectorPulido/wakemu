import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Inspect native protector identity fields without inferring breeds from names. */
public class AuditNpcProtectorIdentity {
 public static void main(String[] args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Object> records=new ArrayList<>();
  apw.bGL().a(new aMD(),new apB<aMD>(){public void load(aMD row){
   if(row.ctC()==424 || row.cpi()==5459 || row.Xt()==5459 || row.ctH()==5459)
    records.add(Map.of("raw",new Gson().toJsonTree(row),"ctC",row.ctC(),"cpi",row.cpi(),"Xt",row.Xt(),"ctH",row.ctH(),"ctJ",row.ctJ(),"ctK",row.ctK(),"cki",row.cki()));
  }});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(records));
  System.out.println("candidate_records="+records.size());
 }
}
