import java.nio.file.*;import java.lang.reflect.*;import java.util.*;import com.google.gson.GsonBuilder;import jdk.internal.org.objectweb.asm.*;
/** Compact eVi prototypes. Only literal boolean-return bytecode is authoritative. */
public final class ExportNativeRunnerOwners {
 static Boolean constant(Method method)throws Exception{
  List<Integer> instructions=new ArrayList<>();
  try(var stream=method.getDeclaringClass().getResourceAsStream("/"+method.getDeclaringClass().getName().replace('.','/')+".class")){
   new ClassReader(stream).accept(new ClassVisitor(Opcodes.ASM8){public void visitPermittedSubclass(String n){}public MethodVisitor visitMethod(int a,String n,String d,String s,String[] e){if(!n.equals(method.getName())||!d.equals("()Z"))return null;return new MethodVisitor(Opcodes.ASM8){public void visitInsn(int op){instructions.add(op);}public void visitVarInsn(int op,int v){instructions.add(-1);}public void visitFieldInsn(int op,String o,String n,String d){instructions.add(-1);}public void visitMethodInsn(int op,String o,String n,String d,boolean i){instructions.add(-1);}public void visitJumpInsn(int op,Label l){instructions.add(-1);}public void visitIntInsn(int op,int n){instructions.add(-1);}public void visitLdcInsn(Object o){instructions.add(-1);}public void visitTypeInsn(int op,String t){instructions.add(-1);}public void visitInvokeDynamicInsn(String n,String d,Handle h,Object...a){instructions.add(-1);}public void visitIincInsn(int v,int n){instructions.add(-1);}public void visitTableSwitchInsn(int a,int b,Label d,Label...l){instructions.add(-1);}public void visitLookupSwitchInsn(Label d,int[]k,Label[]l){instructions.add(-1);}public void visitMultiANewArrayInsn(String d,int n){instructions.add(-1);}};}},ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
  }
  if(instructions.equals(List.of(Opcodes.ICONST_0,Opcodes.IRETURN)))return false;
  if(instructions.equals(List.of(Opcodes.ICONST_1,Opcodes.IRETURN)))return true;
  return null;
 }
 public static void main(String[] args)throws Exception{
  Map<String,Object> rows=new TreeMap<>();int verified=0;
  for(Field f:eVi.class.getDeclaredFields()){
   if(f.getType()!=eVj.class||!Modifier.isStatic(f.getModifiers()))continue;f.setAccessible(true);eVj entry=(eVj)f.get(null);if(entry==null)continue;
   Object runner=entry.bkv();if(!(runner instanceof Qe q))continue;Class<?> cls=q.getClass();Method a=cls.getMethod("bbA"),b=cls.getMethod("bbB");Boolean av=constant(a),bv=constant(b);
   Map<String,Object> row=new LinkedHashMap<>();row.put("runner",cls.getName());row.put("bbA",av);row.put("bbB",bv);row.put("bbA_owner",a.getDeclaringClass().getName());row.put("bbB_owner",b.getDeclaringClass().getName());row.put("literal_constants_verified",av!=null&&bv!=null);if(av!=null&&bv!=null)verified++;rows.put(Integer.toString(entry.d()),row);
  }
  Map<String,Object> out=new LinkedHashMap<>();out.put("source","Installed eVi registry; bbA/bbB literal boolean return bytecode only; null requires runtime authority");out.put("effects",rows);Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(out));System.out.println("Exported "+rows.size()+" prototype owners; "+verified+" literal pairs verified");
 }
}
