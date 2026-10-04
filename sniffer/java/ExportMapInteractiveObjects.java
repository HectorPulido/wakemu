import java.util.*;import java.util.zip.*;import java.nio.file.*;import com.google.gson.*;
/** Installed map environment objects, preserving native object ID/type/payload. */
public class ExportMapInteractiveObjects{
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");List<Map<String,Object>>rows=new ArrayList<>();
  for(Path p:Files.list(Path.of("client/contents/maps/env")).sorted().toList()){
   if(!p.toString().endsWith(".jar"))continue;
   int map=Integer.parseInt(p.getFileName().toString().replace(".jar",""));
   try(ZipFile z=new ZipFile(p.toFile())){
    for(var e:Collections.list(z.entries())){
     if(!e.getName().matches("-?\\d+_-?\\d+"))continue;
     ach a=new ach();try{aoG r=aoG.dx(z.getInputStream(e).readAllBytes());r.aJn();a.a(r);}catch(RuntimeException failure){System.err.println("Skipped unsupported environment chunk "+map+":"+e.getName()+":"+failure.getClass().getSimpleName());continue;}
     if(a.buw()==null)continue;
     for(acq o:a.buw()){bEE type=bEE.cb(o.bkI);if(type==null||!Set.of("Zaap","Drago").contains(type.name()))continue;bEG b=type.bej().bau();b.as(o.azM);rows.add(Map.of("map_id",map,"chunk",e.getName(),"id",o.aHm,"type",type.name(),"x",b.getWorldX(),"y",b.getWorldY(),"z",b.getAltitude(),"auto",o.chb,"payload_hex",HexFormat.of().formatHex(o.azM)));}
    }
   }
  }
  Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(rows));
  System.out.println("Exported "+rows.size()+" native map environment objects");
 }
}
