import java.util.*;import java.util.jar.*;import java.nio.file.*;
import jdk.internal.org.objectweb.asm.*;
/** Reproducible packet family registry: original subclasses of cvB action header. */
public final class ExportNativeActionPackets {
 static record Definition(String parent,Integer opcode){}
 public static void main(String[]args)throws Exception {
  Map<String,Definition> types=new TreeMap<>();
  try(JarFile jar=new JarFile(args[0])){for(var entry:Collections.list(jar.entries())){
   if(!entry.getName().endsWith(".class"))continue;
   String[] identity=new String[2];Integer[] opcode={null};
   new ClassReader(jar.getInputStream(entry)).accept(new ClassVisitor(Opcodes.ASM8){
    public void visitPermittedSubclass(String name){}
    public void visit(int v,int a,String n,String s,String p,String[]i){identity[0]=n;identity[1]=p;}
    public MethodVisitor visitMethod(int a,String n,String d,String s,String[]e){
     if(!n.equals("d")||!d.equals("()I"))return null;
     return new MethodVisitor(Opcodes.ASM8){public void visitIntInsn(int o,int v){opcode[0]=v;}
      public void visitLdcInsn(Object v){if(v instanceof Integer i)opcode[0]=i;}};
    }
   },ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
   types.put(identity[0],new Definition(identity[1],opcode[0]));
  }}
  Map<Integer,String> selected=new TreeMap<>();
  for(var type:types.entrySet()) {
   String parent=type.getValue().parent();boolean action=false;
   while(parent!=null){if(parent.equals("cvB")){action=true;break;}Definition base=types.get(parent);parent=base==null?null:base.parent();}
   if(action&&type.getValue().opcode()!=null)selected.put(type.getValue().opcode(),type.getKey());
  }
  StringBuilder out=new StringBuilder("{\"source\":\"original cvB subclasses; ExportNativeActionPackets\",\"packets\":{");boolean comma=false;
  for(var item:selected.entrySet()){if(comma)out.append(',');comma=true;out.append('"').append(item.getKey()).append("\":\"").append(item.getValue()).append('"');}
  out.append("}}\n");System.out.print(out);
 }
}
