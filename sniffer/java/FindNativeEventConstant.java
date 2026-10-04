import java.util.jar.*;import jdk.internal.org.objectweb.asm.*;
/** Offline bytecode callsite inventory for an actual native event integer. */
public class FindNativeEventConstant {
 public static void main(String[]args)throws Exception{
  int needle=Integer.parseInt(args[1]);try(JarFile jar=new JarFile(args[0])){
   var entries=jar.entries();while(entries.hasMoreElements()){
    var entry=entries.nextElement();if(!entry.getName().endsWith(".class"))continue;
    new ClassReader(jar.getInputStream(entry)).accept(new ClassVisitor(Opcodes.ASM8){
     public void visitPermittedSubclass(String subclass){}
     String owner;public void visit(int v,int access,String name,String signature,String parent,String[]interfaces){owner=name;}
     public MethodVisitor visitMethod(int access,String name,String descriptor,String sig,String[]exceptions){
      return new MethodVisitor(Opcodes.ASM8){
       public void visitIntInsn(int opcode,int value){if(value==needle)System.out.println(owner+"."+name+descriptor+" int="+value);}
       public void visitMethodInsn(int opcode,String target,String method,String desc,boolean iface){
        if(method.equals("ox")&&desc.equals("(I)V")||method.equals("L")&&desc.equals("(B)Z")||method.equals("dr")&&desc.equals("([B)V")||(desc.startsWith("(Ljava/util/BitSet;")&&desc.endsWith("B)Z")))
         System.out.println(owner+"."+name+descriptor+" -> "+target+"."+method+desc);
       }
       public void visitLdcInsn(Object value){if(value instanceof Integer i&&i==needle)System.out.println(owner+"."+name+descriptor+" ldc="+value);}
      };
     }
    },ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
   }
  }
 }
}
