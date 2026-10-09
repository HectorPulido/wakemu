import java.lang.instrument.*;import java.security.ProtectionDomain;
import jdk.internal.org.objectweb.asm.*;
/** Explicit local test policy; no transformation when property is false. */
public final class OpenPlantingAgent {
 public static byte[] patch(String name,byte[] data){
  if(!name.equals("dev")&&!name.equals("ffY"))return null;
  ClassReader reader=new ClassReader(data);ClassWriter writer=new ClassWriter(reader,ClassWriter.COMPUTE_MAXS);
  reader.accept(new ClassVisitor(Opcodes.ASM8,writer){
   public MethodVisitor visitMethod(int access,String method,String desc,String sig,String[] exceptions){
    MethodVisitor output=super.visitMethod(access,method,desc,sig,exceptions);
    if((name.equals("dev")&&method.equals("am")&&desc.equals("(LaBn;)I"))||
       (name.equals("ffY")&&method.equals("C")&&desc.equals("(IS)S"))){
     output.visitCode();output.visitIntInsn(Opcodes.BIPUSH,name.equals("dev")?1:100);
     output.visitInsn(Opcodes.IRETURN);output.visitMaxs(1,3);output.visitEnd();return null;
    }return output;
   }
  },0);return writer.toByteArray();
 }
 public static void premain(String args,Instrumentation instrumentation){
  if(!Boolean.getBoolean("wakfu.local.openPlanting"))return;
  instrumentation.addTransformer(new ClassFileTransformer(){public byte[] transform(ClassLoader loader,String name,Class<?> type,ProtectionDomain domain,byte[] data){return patch(name,data);}});
 }
}
