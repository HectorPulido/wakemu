import java.nio.file.*;import java.io.*;import java.util.*;import java.util.zip.*;import com.google.gson.Gson;
/** All native eVE.fKX exclusion preflight metadata, one offline load. */
public class ExportNativePtPreflight {
 public static void main(String[]args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  List<Integer>clear=new ArrayList<>();Map<Integer,String>areas=new TreeMap<>();int[]count={0};
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){
   count[0]++;eVn e=bcA.dcX().AH(raw.aZE());if(e==null)throw new IllegalStateException("missing"+raw.aZE());
   anc exclusion=e.fKX();if(exclusion==null)clear.add(raw.aZE());else areas.put(raw.aZE(),exclusion.getClass().getName());
  }});Collections.sort(clear);
  Map<String,Object>out=Map.of("source","Installed aNw -> bcA.AH -> eVn.fKX; eVE.a preflight. Nonnull exclusion areas require additional geometry audit.","definitions_checked",count[0],"null_exclusion_references",clear,"nonnull_exclusions",areas);
  try(Writer writer=new OutputStreamWriter(Files.newOutputStream(Path.of(args[0])))){new Gson().toJson(out,writer);}
  System.out.println("preflight checked="+count[0]+" null="+clear.size()+" nonnull="+areas.size());
 }
}
