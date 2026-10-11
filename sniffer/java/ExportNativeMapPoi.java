import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;
/** Decode installed map POI archives with the same native aIm loader as bLa. */
public class ExportNativeMapPoi {
 public static void main(String[] args) throws Exception {
  List<Object> maps = new ArrayList<>();
  List<Object> failures = new ArrayList<>();
  int landmarks=0, interactives=0;
  try (ZipFile zip = new ZipFile("client/contents/maps/data.jar")) {
   for (ZipEntry entry : Collections.list(zip.entries())) {
    if (!entry.getName().matches("poi/\\d+/map\\.poi")) continue;
    int map=Integer.parseInt(entry.getName().split("/")[1]);
    try {
     aIm decoder=new aIm(); decoder.b(aoG.dx(zip.getInputStream(entry).readAllBytes()),false);
     List<acr> points=new ArrayList<>();
     var it=decoder.buC().iterator(); while(it.hasNext()){it.advance();points.add(it.value());}
     List<acq> elements=new ArrayList<>();
     var ie=decoder.cie().iterator();while(ie.hasNext()){ie.advance();elements.add(ie.value());}
     landmarks+=points.size();interactives+=elements.size();
     maps.add(Map.of("map_id",map,"archive_entry",entry.getName(),"landmarks",points,"interactives",elements));
    } catch(Exception failure){failures.add(Map.of("map_id",map,"error",failure.toString()));}
   }
  }
  Map<Integer,String> nativeTypes=new TreeMap<>();
  for(bEE type:bEE.values()) nativeTypes.put((int)type.bei(),type.name());
  Files.writeString(Path.of(args[0]),new GsonBuilder().create().toJson(Map.of("maps",maps,"failures",failures,"native_interactive_types",nativeTypes)));
  System.out.println("maps="+maps.size()+" failures="+failures.size()+" landmarks="+landmarks+" interactives="+interactives);
 }
}
