import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
import com.google.protobuf.Descriptors.Descriptor;
import com.google.protobuf.Descriptors.FileDescriptor;
import com.google.protobuf.DescriptorProtos.FileDescriptorSet;
public class ExportProtocolDescriptors {
 static Map<String,FileDescriptor> files=new TreeMap<>();
 static void add(FileDescriptor file){if(files.putIfAbsent(file.getFullName(),file)==null)for(var dep:file.getDependencies())add(dep);}
 public static void main(String[] args)throws Exception {
  var catalog=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();int success=0;List<String> errors=new ArrayList<>();
  for(var item:catalog.getAsJsonArray("protobuf_classes")) {
   String name=item.getAsString().replace('/','.');
   try {Class<?> type=Class.forName(name,false,ExportProtocolDescriptors.class.getClassLoader());
    for(var method:type.getDeclaredMethods())if(Modifier.isStatic(method.getModifiers())&&method.getParameterCount()==0&&method.getReturnType()==Descriptor.class){method.setAccessible(true);var descriptor=(Descriptor)method.invoke(null);add(descriptor.getFile());success++;break;}
   }catch(Throwable ex){errors.add(name+": "+ex.getClass().getSimpleName());}
  }
  var set=FileDescriptorSet.newBuilder();for(var file:files.values())set.addFile(file.toProto());Files.write(Path.of(args[1]),set.build().toByteArray());
  var info=new LinkedHashMap<String,Object>();info.put("message_classes",success);info.put("proto_files",new ArrayList<>(files.keySet()));info.put("errors",errors);Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(info));
  System.out.println("Exported "+success+" protobuf message descriptors, "+files.size()+" files; errors "+errors.size());
 }
}
