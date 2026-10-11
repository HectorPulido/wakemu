import com.google.protobuf.*;
import com.google.gson.*;
import java.lang.reflect.Field;
import java.util.*;

/** Exports installed intergame message identifiers and original protobuf schemas. */
public final class ExportNativeIntergameDescriptors {
    private static final Map<String,Object> messages = new TreeMap<>();
    private static void collect(Descriptors.Descriptor descriptor) {
        if (messages.containsKey(descriptor.getFullName())) return;
        List<Map<String,Object>> fields = new ArrayList<>();
        messages.put(descriptor.getFullName(), fields);
        for (Descriptors.FieldDescriptor field : descriptor.getFields()) {
            Map<String,Object> info = new LinkedHashMap<>();
            info.put("name",field.getName());info.put("number",field.getNumber());
            info.put("type",field.getType().name());info.put("repeated",field.isRepeated());
            info.put("required",field.isRequired());
            if(field.getContainingOneof()!=null) info.put("oneof",field.getContainingOneof().getName());
            if (field.getJavaType()==Descriptors.FieldDescriptor.JavaType.MESSAGE) {
                info.put("message",field.getMessageType().getFullName());collect(field.getMessageType());
            }
            if (field.getJavaType()==Descriptors.FieldDescriptor.JavaType.ENUM) {
                Map<String,Integer> values=new LinkedHashMap<>();
                for (Descriptors.EnumValueDescriptor value:field.getEnumType().getValues()) values.put(value.getName(),value.getNumber());
                info.put("enum",values);
            }
            fields.add(info);
        }
    }
    public static void main(String[] args)throws Exception {
        Field prototype=aj.class.getDeclaredField("df");prototype.setAccessible(true);
        List<Map<String,Object>> identifiers = new ArrayList<>();
        for (aj entry:aj.values()) {
            MessageLite value=(MessageLite)prototype.get(entry);
            Map<String,Object> info=new LinkedHashMap<>();
            info.put("registry",entry.name());info.put("id",aj.a(value));info.put("java_class",value.getClass().getName());
            for(var method:value.getClass().getDeclaredMethods()) {
                if(java.lang.reflect.Modifier.isStatic(method.getModifiers()) && method.getParameterCount()==0 && method.getReturnType()==Descriptors.Descriptor.class) {
                    Descriptors.Descriptor descriptor=(Descriptors.Descriptor)method.invoke(null);
                    info.put("message",descriptor.getFullName());collect(descriptor);break;
                }
            }
            identifiers.add(info);
        }
        for(Class<?> envelope:List.of(am.class,aq.class,au.class,ay.class)) {
            for(var method:envelope.getDeclaredMethods()) if(java.lang.reflect.Modifier.isStatic(method.getModifiers()) && method.getParameterCount()==0 && method.getReturnType()==Descriptors.Descriptor.class) {collect((Descriptors.Descriptor)method.invoke(null));break;}
        }
        Map<String,Object> result=new LinkedHashMap<>();result.put("identifiers",identifiers);result.put("messages",messages);
        System.out.println(new GsonBuilder().setPrettyPrinting().create().toJson(result));
    }
}
