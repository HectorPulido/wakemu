import java.util.jar.*;import java.util.*;import jdk.internal.org.objectweb.asm.*;
/** Offline exact-owner/name GETFIELD/GETSTATIC consumer audit; no substring guessing. */
public class FindNativeFieldConsumers {
 public static void main(String[]args)throws Exception{
  try(JarFile jar=new JarFile(args[0])){
   for(var entry:Collections.list(jar.entries())){
    if(!entry.getName().endsWith(".class"))continue;
    new ClassReader(jar.getInputStream(entry)).accept(new ClassVisitor(Opcodes.ASM8){
     public void visitPermittedSubclass(String name){}
     public MethodVisitor visitMethod(int access,String name,String descriptor,String signature,String[] exceptions){
      return new MethodVisitor(Opcodes.ASM8){
       public void visitFieldInsn(int opcode,String owner,String field,String descriptor){
        if(owner.equals(args[1])&&field.equals(args[2]))
         System.out.println(entry.getName()+" "+name+" -> "+opcode+" "+owner+"."+field+descriptor);
       }
      };
     }
    },ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
   }
  }
 }
}
