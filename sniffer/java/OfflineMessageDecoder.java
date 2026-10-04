import java.nio.file.*;
import java.nio.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
import com.google.protobuf.ByteString;
import com.google.protobuf.Message;
import com.google.protobuf.DynamicMessage;
import com.google.protobuf.Descriptors.Descriptor;
public class OfflineMessageDecoder {
 static Gson gson=new GsonBuilder().serializeNulls().create();
 static Object fields(Object value,int depth,Set<Object> seen)throws Exception {
  if(value==null||value instanceof String||value instanceof Number||value instanceof Boolean||value instanceof Character)return value;
  if(value instanceof Enum<?>)return ((Enum<?>)value).name();
  if(value instanceof ByteString)return Map.of("base64",Base64.getEncoder().encodeToString(((ByteString)value).toByteArray()));
  if(value instanceof Message) {
   try {var message=(Message)value;Descriptor descriptor=null;
    if(value instanceof DynamicMessage)descriptor=message.getDescriptorForType();
    else for(Method method:value.getClass().getDeclaredMethods())if(Modifier.isStatic(method.getModifiers())&&method.getParameterCount()==0&&method.getReturnType()==Descriptor.class){method.setAccessible(true);descriptor=(Descriptor)method.invoke(null);break;}
    if(descriptor!=null){var dynamic=DynamicMessage.parseFrom(descriptor,message.toByteArray());Map<String,Object> proto=new LinkedHashMap<>();proto.put("protobuf_type",descriptor.getFullName());Map<String,Object> contents=new LinkedHashMap<>();for(var entry:dynamic.getAllFields().entrySet())contents.put(entry.getKey().getName(),fields(entry.getValue(),depth+1,seen));proto.put("fields",contents);return proto;}
   }catch(Exception ignored){}
  }
  if(value instanceof byte[])return Map.of("bytes",((byte[])value).length,"base64",Base64.getEncoder().encodeToString((byte[])value));
  if(value instanceof java.util.concurrent.atomic.AtomicReference<?>)return fields(((java.util.concurrent.atomic.AtomicReference<?>)value).get(),depth,seen);
  if(value instanceof java.util.concurrent.atomic.AtomicInteger)return ((java.util.concurrent.atomic.AtomicInteger)value).get();
  if(value instanceof java.util.concurrent.atomic.AtomicLong)return ((java.util.concurrent.atomic.AtomicLong)value).get();
  if(depth>4||!seen.add(value))return Map.of("class",value.getClass().getName(),"opaque",true);
  if(value.getClass().isArray()){List<Object> arr=new ArrayList<>();for(int i=0;i<Array.getLength(value);i++)arr.add(fields(Array.get(value,i),depth+1,seen));return arr;}
  if(value instanceof Collection<?>){List<Object> arr=new ArrayList<>();for(Object obj:(Collection<?>)value)arr.add(fields(obj,depth+1,seen));return arr;}
  if(value instanceof Map<?,?>){Map<String,Object> arr=new LinkedHashMap<>();for(var e:((Map<?,?>)value).entrySet())arr.put(String.valueOf(e.getKey()),fields(e.getValue(),depth+1,seen));return arr;}
  Map<String,Object> out=new LinkedHashMap<>();out.put("class",value.getClass().getName());
  for(Class<?> c=value.getClass();c!=null&&!c.getName().equals("aAa")&&!c.getName().startsWith("java.");c=c.getSuperclass())
   for(Field f:c.getDeclaredFields())if(!Modifier.isStatic(f.getModifiers())){if(f.trySetAccessible())out.put(f.getName(),fields(f.get(value),depth+1,seen));}
  return out;
 }
 public static void main(String[] args)throws Exception {
  JsonObject catalog=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
  Map<Integer,String> classes=new HashMap<>();Set<String> observed=new HashSet<>();
  for(JsonElement e:JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonArray())observed.add(e.getAsString());
  for(JsonElement e:catalog.getAsJsonArray("messages")){JsonObject m=e.getAsJsonObject();if(observed.contains(m.get("class").getAsString()))classes.put(m.get("opcode").getAsInt(),m.get("class").getAsString());}
  int success=0,failed=0;
  try(var out=Files.newBufferedWriter(Path.of(args[3]))) {
   for(String line:Files.readAllLines(Path.of(args[1]))) {
    JsonObject frame=JsonParser.parseString(line).getAsJsonObject();
    if(!frame.get("direction").getAsString().equals("in"))continue;
    String cls=classes.get(frame.get("opcode").getAsInt());frame.addProperty("message_class",cls);
    try {
     Class<?> type=Class.forName(cls);Object msg=type.getConstructor().newInstance();
     byte[] body=Base64.getDecoder().decode(frame.get("body_base64").getAsString());
     boolean accepted=(boolean)type.getMethod("dp",byte[].class).invoke(msg,(Object)body);
     frame.addProperty("decoder_return",accepted);frame.addProperty("extraction_status","fields_extracted");frame.add("fields",gson.toJsonTree(fields(msg,0,Collections.newSetFromMap(new IdentityHashMap<>()))));
     if(accepted)success++;else failed++;
    }catch(Throwable ex){Throwable cause=ex instanceof InvocationTargetException?ex.getCause():ex;frame.addProperty("extraction_status","exception");frame.addProperty("decode_error",cause.getClass().getName()+": "+cause.getMessage());failed++;}
    out.write(gson.toJson(frame));out.newLine();
   }
  }
  System.out.println("Inbound dp() returned true: "+success+"; returned false or threw: "+failed);
 }
}
