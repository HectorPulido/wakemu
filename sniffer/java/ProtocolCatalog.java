import java.nio.file.*;
import java.util.*;
import java.util.jar.*;
import jdk.internal.org.objectweb.asm.*;
import com.google.gson.GsonBuilder;
public class ProtocolCatalog {
 static Map<String,Map<String,Object>> all=new TreeMap<>();
 static List<Map<String,Object>> methods=new ArrayList<>();
 static boolean inherits(String name,String base) {
  Set<String> seen=new HashSet<>();
  while(name!=null && seen.add(name)) {if(name.equals(base))return true; var m=all.get(name); if(m==null)return false;name=(String)m.get("super");}return false;
 }
 public static void main(String[] args)throws Exception {
  try(JarFile jar=new JarFile(args[0])) {
   var entries=jar.entries();while(entries.hasMoreElements()) {var entry=entries.nextElement();if(!entry.getName().endsWith(".class"))continue;
    ClassReader reader=new ClassReader(jar.getInputStream(entry));
    reader.accept(new ClassVisitor(Opcodes.ASM8) {
     public void visitPermittedSubclass(String name) {}
     Map<String,Object> item=new LinkedHashMap<>(); List<Map<String,Object>> fields=new ArrayList<>(); List<String> calls=new ArrayList<>();
     public void visit(int v,int a,String n,String sig,String sup,String[] interfaces){item.put("class",n);item.put("super",sup);item.put("abstract",(a&Opcodes.ACC_ABSTRACT)!=0);item.put("interfaces",Arrays.asList(interfaces));item.put("fields",fields);all.put(n,item);}
     public FieldVisitor visitField(int a,String n,String d,String sig,Object val){if((a&Opcodes.ACC_STATIC)==0)fields.add(Map.of("name",n,"descriptor",d));return null;}
     public MethodVisitor visitMethod(int a,String n,String d,String sig,String[] exc) {
      if(n.equals("d")&&d.equals("()I"))return new MethodVisitor(Opcodes.ASM8) {
       Integer constant; boolean simple=true;
       public void visitIntInsn(int opcode,int value){if(opcode==Opcodes.BIPUSH||opcode==Opcodes.SIPUSH)constant=value;else simple=false;}
       public void visitLdcInsn(Object value){if(value instanceof Integer)constant=(Integer)value;else simple=false;}
       public void visitInsn(int opcode){if(opcode>=Opcodes.ICONST_M1&&opcode<=Opcodes.ICONST_5)constant=opcode-Opcodes.ICONST_0; else if(opcode==Opcodes.IRETURN&&simple&&constant!=null)item.put("opcode",constant);else simple=false;}
       public void visitVarInsn(int o,int v){simple=false;}public void visitFieldInsn(int o,String ow,String n,String ds){simple=false;}public void visitMethodInsn(int o,String ow,String n,String ds,boolean it){simple=false;}
      };
      Map<String,Object> method=new LinkedHashMap<>();method.put("class",item.get("class"));method.put("method",n+d);Set<String> refs=new TreeSet<>();List<String> strings=new ArrayList<>();method.put("references",refs);method.put("strings",strings);methods.add(method);
      return new MethodVisitor(Opcodes.ASM8) {
       public void visitTypeInsn(int o,String t){refs.add(t);}
       public void visitFieldInsn(int o,String ow,String na,String ds){refs.add(ow);}
       public void visitLdcInsn(Object v){if(v instanceof String)strings.add((String)v);}
       public void visitMethodInsn(int o,String owner,String name,String desc,boolean it){refs.add(owner);if(n.equals("dp")||n.equals("aWH")||n.equals("eX"))calls.add(n+": "+owner+"."+name+desc);}
       public void visitEnd(){item.put("codec_calls",calls);}
      };
     }
    },ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
   }
  }
  List<Map<String,Object>> messages=new ArrayList<>();
  for(var entry:all.entrySet()) {String n=entry.getKey();var m=entry.getValue();if((inherits(n,"Nx")||inherits(n,"Nt"))&&m.containsKey("opcode")) {m.put("direction",inherits(n,"Nx")?"out":"in");messages.add(m);}}
  Set<String> messageNames=new HashSet<>();for(var m:messages)messageNames.add((String)m.get("class"));
  Map<String,List<Map<String,Object>>> references=new TreeMap<>();
  for(var method:methods)for(String reference:(Set<String>)method.get("references"))if(messageNames.contains(reference)) {Map<String,Object> info=new LinkedHashMap<>(method);info.remove("references");references.computeIfAbsent(reference,k->new ArrayList<>()).add(info);}
  for(var m:messages) {List<Map<String,Object>> inheritedFields=new ArrayList<>();String parent=(String)m.get("super");while(parent!=null&&all.containsKey(parent)&&!parent.equals("aAa")){var pm=all.get(parent);for(var f:(List<Map<String,Object>>)pm.get("fields")){var copy=new LinkedHashMap<>(f);copy.put("declared_in",parent);inheritedFields.add(copy);}parent=(String)pm.get("super");}m.put("inherited_fields",inheritedFields);}
  Map<String,Object> output=new LinkedHashMap<>();output.put("messages",messages);output.put("references",references);List<String> protobufClasses=new ArrayList<>();for(String n:all.keySet())if(inherits(n,"com/google/protobuf/GeneratedMessageV3"))protobufClasses.add(n);output.put("protobuf_classes",protobufClasses);
  List<Map<String,Object>> dirs=new ArrayList<>();
  for(Object dir:aAS.values()) {aAS d=(aAS)dir;dirs.add(Map.of("name",d.name(),"id",d.dyI,"dx",d.dyJ,"dy",d.dyK));}
  output.put("directions",dirs);List<Map<String,Object>> modes=new ArrayList<>();for(ada m:ada.values())modes.add(Map.of("name",m.name(),"id",m.d()));output.put("movement_modes",modes);
  Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(output));
  System.out.println("Catalogued "+messages.size()+" message classes from "+all.size()+" classes.");
 }
}
