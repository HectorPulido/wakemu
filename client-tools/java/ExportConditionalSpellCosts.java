import java.nio.file.*;import java.util.*;import java.lang.reflect.*;
/** Native conditional tables; raw criteria preserved, no guessed conditions. */
public class ExportConditionalSpellCosts {
 public static void main(String[]a)throws Exception{
 List<String>out=new ArrayList<>();Method convert=bPS.class.getDeclaredMethod("a",aNs.class);convert.setAccessible(true);
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 apw.bGL().a(new aNr(),new apB<aNr>(){public void load(aNr r){out.add(r.d()+"\tCATEGORIES\t"+Arrays.toString(r.ckE()==null?new int[0]:r.ckE()));if(r.cwI()==null)return;for(Map.Entry<String,aNs>e:r.cwI().entrySet())try{
 fyP p=(fyP)convert.invoke(null,e.getValue());StringBuilder s=new StringBuilder(r.d()+"\t"+Base64.getEncoder().encodeToString(e.getKey().getBytes(java.nio.charset.StandardCharsets.UTF_8))+"\t"+eQe.tz(e.getKey()).getClass().getName()+"\t"+Arrays.toString(r.ckE()==null?new int[0]:r.ckE()));
 for(int l=1;l<=200;l++)s.append("\t").append(p.c(ffw.sgD,l)).append(",").append(p.c(ffw.sgE,l)).append(",").append(p.c(ffw.sgF,l));out.add(s.toString());
 }catch(Exception ex){throw new RuntimeException(ex);}}});Files.write(Path.of(a[0]),out);System.out.println("Native conditional rules "+out.size());
 }}
