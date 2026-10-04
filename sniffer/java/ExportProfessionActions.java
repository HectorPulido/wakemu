import java.nio.file.*;import java.util.*;import com.google.gson.*;
public class ExportProfessionActions {
 public static void main(String[]args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Object>animations=new ArrayList<>();List<Integer>professions=new ArrayList<>();
  apw.bGL().a(new aNq(),new apB<aNq>(){public void load(aNq r){animations.add(Map.of("id",r.d(),"name",r.cvQ(),"animation",r.cvN(),"suffix",r.cvO(),"items",r.cvP()));}});
  apw.bGL().a(new aKL(),new apB<aKL>(){public void load(aKL r){professions.add(r.cmG());}});
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("animations",animations,"profession_ids",professions,"source","installed aNq/aKL bdata, aZB/bah loaders")));
 }
}
