import java.util.jar.*;import java.util.*;import jdk.internal.org.objectweb.asm.*;
/** Exact owner/name/optional-descriptor method consumers, offline bytecode only. */
public class FindNativeMethodConsumers {
 public static void main(String[]args)throws Exception{
  try(JarFile jar=new JarFile(args[0])){
   for(var entry:Collections.list(jar.entries())){
    if(!entry.getName().endsWith(".class"))continue;
    new ClassReader(jar.getInputStream(entry)).accept(new ClassVisitor(Opcodes.ASM8){
     public void visitPermittedSubclass(String name){}
     public MethodVisitor visitMethod(int access,String name,String descriptor,String signature,String[] exceptions){
      return new MethodVisitor(Opcodes.ASM8){
       public void visitMethodInsn(int opcode,String owner,String method,String descriptor,boolean iface){
        if((args[1].equals("*")||owner.equals(args[1]))&&method.equals(args[2])&&(args.length<4||descriptor.equals(args[3])))
         System.out.println(entry.getName()+" "+name+" -> "+owner+"."+method+descriptor);
       }
      };
     }
    },ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
   }
  }
 }
}
