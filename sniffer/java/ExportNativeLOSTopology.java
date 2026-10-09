import java.util.*;import java.util.zip.*;import java.nio.file.*;import java.io.*;import com.google.gson.*;
/** Actual VB.a(Vz[]) ordered columns for Sf.bfX, not walkable-only Vy cells. */
public class ExportNativeLOSTopology {
 public static void main(String[]args)throws Exception {
  if(args[0].equals("--all")) {
   try(var maps=Files.list(Path.of("client/contents/maps/tplg"))) {
    for(Path archive:maps.filter(p->p.getFileName().toString().matches("\\d+\\.jar")).sorted().toList()) {
     int map=Integer.parseInt(archive.getFileName().toString().replace(".jar",""));
     Path output=Path.of(args[1],map+".json");
     if(!Files.isRegularFile(output)) {
      try { export(map,output); }
      catch(Exception failure) {
       Files.deleteIfExists(output);
       Throwable cause=failure; while(cause.getCause()!=null) cause=cause.getCause();
       System.err.println("FAILED map="+map+" reason="+cause.getClass().getSimpleName()+" detail="+failure.getMessage());
      }
     }
    }
   }
   return;
  }
  export(Integer.parseInt(args[0]),Path.of(args[1]));
 }
 static void export(int map,Path output)throws Exception {
  List<Object>columns=new ArrayList<>();
  try(ZipFile archive=new ZipFile("client/contents/maps/tplg/"+map+".jar")){
   List<? extends ZipEntry>entries=Collections.list(archive.entries());entries.sort(Comparator.comparing(ZipEntry::getName));
   for(var entry:entries)if(entry.getName().matches("-?\\d+_-?\\d+")){
    byte[] bytes=archive.getInputStream(entry).readAllBytes();
    aoG reader=aoG.dx(bytes); VB chunk=VC.ag(reader.aJn());
    try { chunk.a(reader); } catch (RuntimeException failure) {
     throw new IOException("Native chunk decode failed: map="+map+" entry="+entry.getName()+" bytes="+bytes.length+" type="+chunk.getClass().getSimpleName(),failure);
    }
    for(int x=chunk.bbn;x<chunk.bbn+18;x++)for(int y=chunk.bbo;y<chunk.bbo+18;y++){
     Vz[]surfaces=new Vz[32];for(int i=0;i<32;i++)surfaces[i]=new Vz();
     int count=chunk.a(x,y,surfaces,0);if(count==0)continue;
     List<Object>values=new ArrayList<>();for(int i=0;i<count;i++)values.add(List.of((int)surfaces[i].bbl,(int)surfaces[i].aYX,surfaces[i].bLf));
     columns.add(List.of(x,y,values));
    }
   }
  }
  Files.createDirectories(output.getParent());
  try(Writer writer=new OutputStreamWriter(Files.newOutputStream(output))){
   new Gson().toJson(Map.of("schema","native-Sf-Vz-columns-v1","map_id",map,"columns",columns,"source","Installed VB.a(x,y,Vz[],0): bbl surface altitude, signed aYX height, bLf LOS transparency; original order retained"),writer);
  }
  System.out.println("map="+map+" columns="+columns.size());
 }
}
