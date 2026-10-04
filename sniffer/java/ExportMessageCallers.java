import java.nio.file.*;
import java.util.*;
import java.util.jar.*;
import jdk.internal.org.objectweb.asm.*;
/** Offline codec caller graph. Edges identify source consumers, not semantic proof. */
public class ExportMessageCallers {
    public static void main(String[]args)throws Exception{
        Set<String> targets=new HashSet<>(Files.readAllLines(Path.of(args[1])));
        TreeSet<String> output=new TreeSet<>();
        try(JarFile jar=new JarFile(args[0])){
            var entries=jar.entries();
            while(entries.hasMoreElements()){
                var entry=entries.nextElement();if(!entry.getName().endsWith(".class"))continue;
                String caller=entry.getName().replace(".class","");
                new ClassReader(jar.getInputStream(entry)).accept(new ClassVisitor(Opcodes.ASM8){
                    public void visitPermittedSubclass(String name) {}
                    public MethodVisitor visitMethod(int access,String name,String descriptor,String signature,String[] exceptions){
                        return new MethodVisitor(Opcodes.ASM8){
                            public void visitMethodInsn(int opcode,String owner,String method,String desc,boolean itf){
                                if(targets.contains(owner)&&!caller.equals(owner))
                                    output.add(owner+"\t"+caller+"\t"+name+descriptor+"\t"+method+desc);
                            }
                        };
                    }
                },ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
            }
        }
        Files.write(Path.of(args[2]),output);
        System.out.println("Exported "+output.size()+" message-consumer edges");
    }
}
