import java.lang.instrument.*;import java.security.ProtectionDomain;
import jdk.internal.org.objectweb.asm.*;
/** Explicit local test policy; no transformation when property is false. */
public final class OpenPlantingAgent {
 private static final String DUNGEON_CONSTRUCTOR="(IIIIISLaAS;Lamb;ISISZSZZI)V";
 public static Object dungeonCriterion(int destination,Object original){
  if(!Boolean.getBoolean("wakfu.local.openDungeonMissions"))return original;
  try {
   java.util.Properties rules=new java.util.Properties();
   try(var input=OpenPlantingAgent.class.getResourceAsStream("/dungeon-entry-overrides.properties")){
    if(input==null)throw new IllegalStateException("Missing dungeon entry policy resource");rules.load(input);
   }
   String expression=rules.getProperty(Integer.toString(destination));
   if(expression==null)return original;
   ClassLoader loader=original.getClass().getClassLoader();
   Class<?> base=Class.forName("amb",false,loader);
   var nativePath=java.nio.file.Path.of(base.getProtectionDomain().getCodeSource().getLocation().toURI());
   String digest=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(java.nio.file.Files.readAllBytes(nativePath)));
   if(!digest.equals(rules.getProperty("native_sha256")))throw new IllegalStateException("Dungeon entry native client version mismatch");
   Class<?> charStream=Class.forName("org.antlr.runtime.CharStream",true,loader);
   Object chars=Class.forName("org.antlr.runtime.ANTLRStringStream",true,loader).getConstructor(String.class).newInstance(expression);
   Class<?> lexerClass=Class.forName("eQb",true,loader);Object lexer=lexerClass.getConstructor(charStream).newInstance(chars);
   Class<?> tokenSource=Class.forName("org.antlr.runtime.TokenSource",true,loader);
   Class<?> tokensClass=Class.forName("org.antlr.runtime.CommonTokenStream",true,loader);Object tokens=tokensClass.getConstructor(tokenSource).newInstance(lexer);
   Class<?> parserClass=Class.forName("eQd",true,loader);Object parser=parserClass.getConstructor(Class.forName("org.antlr.runtime.TokenStream",true,loader)).newInstance(tokens);
   var values=(java.util.List<?>)parserClass.getMethod("fGv").invoke(parser);
   if((Integer)lexerClass.getMethod("getNumberOfSyntaxErrors").invoke(lexer)!=0 || (Integer)parserClass.getMethod("getNumberOfSyntaxErrors").invoke(parser)!=0 || (Integer)tokensClass.getMethod("LA",int.class).invoke(tokens,1)!=-1 || values.isEmpty())throw new IllegalStateException("Invalid projected native entrance criterion");
   Object result=values.get(values.size()-1);if(!base.isInstance(result))throw new IllegalStateException("Native entrance projection is not boolean");return result;
  }catch(Exception error){throw new IllegalStateException("Cannot apply scoped dungeon entrance policy",error);}
 }
 public static byte[] patch(String name,byte[] data){
  if(name.equals("flF") && Boolean.getBoolean("wakfu.local.openDungeonMissions")){
   ClassReader reader=new ClassReader(data);ClassWriter writer=new ClassWriter(reader,ClassWriter.COMPUTE_MAXS);int[] matches={0};
   reader.accept(new ClassVisitor(Opcodes.ASM8,writer){public MethodVisitor visitMethod(int access,String method,String desc,String sig,String[] exceptions){
    MethodVisitor output=super.visitMethod(access,method,desc,sig,exceptions);
    if(method.equals("<init>")&&desc.equals(DUNGEON_CONSTRUCTOR)){matches[0]++;return new MethodVisitor(Opcodes.ASM8,output){public void visitCode(){super.visitCode();super.visitVarInsn(Opcodes.ILOAD,1);super.visitVarInsn(Opcodes.ALOAD,8);super.visitMethodInsn(Opcodes.INVOKESTATIC,"OpenPlantingAgent","dungeonCriterion","(ILjava/lang/Object;)Ljava/lang/Object;",false);super.visitTypeInsn(Opcodes.CHECKCAST,"amb");super.visitVarInsn(Opcodes.ASTORE,8);}};}return output;
   }},0);if(matches[0]!=1)throw new IllegalStateException("Unexpected native dungeon constructor boundary");return writer.toByteArray();
  }
  if(Boolean.getBoolean("wakfu.local.openPlanting") && (name.equals("cYt") || name.equals("dev") || name.equals("cYv"))){
   ClassReader queueReader=new ClassReader(data);ClassWriter queueWriter=new ClassWriter(queueReader,ClassWriter.COMPUTE_MAXS);
   int[] queueBoundaries={0,0,0,0};
   queueReader.accept(new ClassVisitor(Opcodes.ASM8,queueWriter){public MethodVisitor visitMethod(int access,String method,String desc,String sig,String[] exceptions){
    MethodVisitor output=super.visitMethod(access,method,desc,sig,exceptions);
    if(name.equals("cYt")&&method.equals("ah")&&desc.equals("(LaBn;)Z"))return new MethodVisitor(Opcodes.ASM8,output){public void visitIntInsn(int opcode,int operand){if(opcode==Opcodes.BIPUSH&&operand==98){queueBoundaries[0]++;super.visitVarInsn(Opcodes.ALOAD,0);super.visitMethodInsn(Opcodes.INVOKESTATIC,"OpenPlantingAgentRecovery","waitingLimit","(Ljava/lang/Object;)I",false);}else super.visitIntInsn(opcode,operand);}};
    if(name.equals("cYt")&&method.equals("a")&&desc.equals("(LcYy;)Z")){queueBoundaries[1]++;return new MethodVisitor(Opcodes.ASM8,output){public void visitCode(){super.visitCode();super.visitVarInsn(Opcodes.ALOAD,0);super.visitVarInsn(Opcodes.ALOAD,1);super.visitMethodInsn(Opcodes.INVOKESTATIC,"OpenPlantingAgentRecovery","pending","(Ljava/lang/Object;Ljava/lang/Object;)V",false);}};}
    if(name.equals("cYv")&&method.equals("pathEnded")&&desc.equals("(LacS;IIS)V")){queueBoundaries[2]++;return new MethodVisitor(Opcodes.ASM8,output){public void visitCode(){super.visitCode();super.visitVarInsn(Opcodes.ALOAD,0);super.visitMethodInsn(Opcodes.INVOKESTATIC,"OpenPlantingAgentRecovery","acceptCallback","(Ljava/lang/Object;)Z",false);Label current=new Label();super.visitJumpInsn(Opcodes.IFNE,current);super.visitInsn(Opcodes.RETURN);super.visitLabel(current);super.visitFrame(Opcodes.F_SAME,0,null,0,null);}};}
    if(name.equals("dev")&&method.equals("fb")&&desc.equals("(II)V")){queueBoundaries[3]++;return new MethodVisitor(Opcodes.ASM8,output){public void visitCode(){super.visitCode();super.visitVarInsn(Opcodes.ALOAD,0);super.visitVarInsn(Opcodes.ILOAD,1);super.visitVarInsn(Opcodes.ILOAD,2);super.visitMethodInsn(Opcodes.INVOKESTATIC,"OpenPlantingAgentRecovery","beginRequest","(Ljava/lang/Object;II)Z",false);Label allowed=new Label();super.visitJumpInsn(Opcodes.IFNE,allowed);super.visitInsn(Opcodes.RETURN);super.visitLabel(allowed);super.visitFrame(Opcodes.F_SAME,0,null,0,null);}};}
    return output;
   }},0);if((name.equals("cYt")&&(queueBoundaries[0]!=1||queueBoundaries[1]!=1))||(name.equals("cYv")&&queueBoundaries[2]!=1)||(name.equals("dev")&&queueBoundaries[3]!=1))throw new IllegalStateException("Unexpected native planting queue boundary: "+name);data=queueWriter.toByteArray();if(OpenPlantingAgentRecovery.diagnosticsEnabled())System.err.println("[PlantingQueueRecovery] transformed="+name+" boundaries="+java.util.Arrays.toString(queueBoundaries));if(name.equals("cYt")||name.equals("cYv"))return data;
  }
  if(!Boolean.getBoolean("wakfu.local.openPlanting")||(!name.equals("dev")&&!name.equals("ffY")))return null;
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
  if(!Boolean.getBoolean("wakfu.local.openPlanting")&&!Boolean.getBoolean("wakfu.local.openDungeonMissions"))return;
  instrumentation.addTransformer(new ClassFileTransformer(){public byte[] transform(ClassLoader loader,String name,Class<?> type,ProtectionDomain domain,byte[] data){return patch(name,data);}});
 }
}
