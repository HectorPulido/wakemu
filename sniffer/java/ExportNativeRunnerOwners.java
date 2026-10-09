import java.nio.file.*;import java.lang.reflect.*;import java.util.*;import com.google.gson.GsonBuilder;import jdk.internal.org.objectweb.asm.*;
/** Prove literal, transparent-super and immutable configured-field owner routing. */
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
 record Instruction(int opcode, int variable, String owner, String name, String descriptor) {}
 record Proof(Boolean value, String kind, String source) {}
 static List<Instruction> instructions(Class<?> owner, String method, String descriptor)throws Exception {
  List<Instruction> result=new ArrayList<>();
  try(var stream=owner.getResourceAsStream("/"+owner.getName().replace('.','/')+".class")) {
   new ClassReader(stream).accept(new ClassVisitor(Opcodes.ASM8) {
    public void visitPermittedSubclass(String name) {}
    public MethodVisitor visitMethod(int access,String name,String desc,String signature,String[] exceptions) {
     if(!name.equals(method)||!desc.equals(descriptor))return null;
     return new MethodVisitor(Opcodes.ASM8) {
      void add(int op,int var,String o,String n,String d){result.add(new Instruction(op,var,o,n,d));}
      public void visitInsn(int op){add(op,-1,null,null,null);}
      public void visitVarInsn(int op,int var){add(op,var,null,null,null);}
      public void visitFieldInsn(int op,String o,String n,String d){add(op,-1,o,n,d);}
      public void visitMethodInsn(int op,String o,String n,String d,boolean iface){add(op,-1,o,n,d);}
      public void visitJumpInsn(int op,Label label){add(-1,-1,null,null,null);}
      public void visitIntInsn(int op,int value){add(-1,-1,null,null,null);}
      public void visitLdcInsn(Object value){add(-1,-1,null,null,null);}
      public void visitTypeInsn(int op,String type){add(-1,-1,null,null,null);}
      public void visitInvokeDynamicInsn(String n,String d,Handle h,Object...args){add(-1,-1,null,null,null);}
      public void visitIincInsn(int v,int n){add(-1,-1,null,null,null);}
      public void visitTableSwitchInsn(int a,int b,Label d,Label...labels){add(-1,-1,null,null,null);}
      public void visitLookupSwitchInsn(Label d,int[] keys,Label[] labels){add(-1,-1,null,null,null);}
      public void visitMultiANewArrayInsn(String d,int n){add(-1,-1,null,null,null);}
     };
    }
   },ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
  }
  return result;
 }
 static boolean aload(Instruction instruction,int variable) {
  return instruction.opcode()==Opcodes.ALOAD && instruction.variable()==variable;
 }
 static boolean sameField(Instruction instruction,Field field) {
  return field.getDeclaringClass().getName().replace('.','/').equals(instruction.owner())
   && field.getName().equals(instruction.name()) && "Z".equals(instruction.descriptor());
 }
 static boolean immutableConfiguration(Field field)throws Exception {
  // A private field cannot be written directly by unrelated runner classes.
  if(field.getType()!=boolean.class||!Modifier.isPrivate(field.getModifiers()))return false;
  Class<?> owner=field.getDeclaringClass();
  List<String[]> methods=new ArrayList<>();
  try(var stream=owner.getResourceAsStream("/"+owner.getName().replace('.','/')+".class")) {
   new ClassReader(stream).accept(new ClassVisitor(Opcodes.ASM8) {
    public void visitPermittedSubclass(String name) {}
    public MethodVisitor visitMethod(int access,String name,String desc,String sig,String[] ex) {
     methods.add(new String[]{name,desc});return null;
    }
   },ClassReader.SKIP_DEBUG|ClassReader.SKIP_FRAMES);
  }
  boolean initialized=false;
  for(String[] method:methods) {
   List<Instruction> code=instructions(owner,method[0],method[1]);
   for(int i=0;i<code.size();i++)if(code.get(i).opcode()==Opcodes.PUTFIELD&&sameField(code.get(i),field)) {
    if(i<2)return false;
    Instruction value=code.get(i-1);
    if(method[0].equals("<init>")&&aload(code.get(i-2),0)
      && (value.opcode()==Opcodes.ICONST_0||value.opcode()==Opcodes.ICONST_1||value.opcode()==Opcodes.ILOAD)) {
     initialized=true;continue;
    }
    // Clone configuration copies must read this same field from the source receiver.
    if(i>=3&&value.opcode()==Opcodes.GETFIELD&&sameField(value,field)
      &&aload(code.get(i-2),0)&&code.get(i-3).opcode()==Opcodes.ALOAD
      &&code.get(i-3).variable()!=0)continue;
    return false;
   }
  }
  return initialized;
 }
 static Proof prove(Method method,Object runner,Set<String> seen)throws Exception {
  String key=method.getDeclaringClass().getName()+"."+method.getName();
  if(!seen.add(key))return new Proof(null,"unresolved",key);
  Boolean literal=constant(method);
  if(literal!=null)return new Proof(literal,"literal",key);
  List<Instruction> code=instructions(method.getDeclaringClass(),method.getName(),"()Z");
  if(code.size()==3&&aload(code.get(0),0)&&code.get(2).opcode()==Opcodes.IRETURN) {
   Instruction middle=code.get(1);
   if(middle.opcode()==Opcodes.INVOKESPECIAL&&middle.name().equals(method.getName())&&middle.descriptor().equals("()Z")) {
    Method parent=Class.forName(middle.owner().replace('/','.')).getMethod(middle.name());
    Proof inherited=prove(parent,runner,seen);
    return new Proof(inherited.value(),inherited.value()==null?"unresolved":"super_delegate",key+" -> "+inherited.source());
   }
   if(middle.opcode()==Opcodes.GETFIELD&&middle.descriptor().equals("Z")) {
    Field field=Class.forName(middle.owner().replace('/','.')).getDeclaredField(middle.name());
    if(immutableConfiguration(field)) {
     field.setAccessible(true);
     return new Proof(field.getBoolean(runner),"immutable_registry_configuration",key+" -> "+middle.owner()+"."+middle.name());
    }
   }
  }
  return new Proof(null,"unresolved",key);
 }
 public static void main(String[] args)throws Exception{
  Map<String,Object> rows=new TreeMap<>();int verified=0,clones=0;
  for(Field f:eVi.class.getDeclaredFields()){
   if(f.getType()!=eVj.class||!Modifier.isStatic(f.getModifiers()))continue;
   f.setAccessible(true);eVj entry=(eVj)f.get(null);if(entry==null)continue;
   Object runner=entry.bkv();if(!(runner instanceof Qe q))continue;
   Class<?> cls=q.getClass();Method a=cls.getMethod("bbA"),b=cls.getMethod("bbB");
   Proof av=prove(a,runner,new HashSet<>()),bv=prove(b,runner,new HashSet<>());
   boolean proven=av.value()!=null&&bv.value()!=null;
   if(proven) {
    Qe clone=(Qe)q.bbn();
    if(q.bbA()!=av.value()||q.bbB()!=bv.value()||clone.bbA()!=av.value()||clone.bbB()!=bv.value())
     throw new IllegalStateException("Native prototype/clone proof mismatch: "+entry.d());
    verified++;clones++;
   }
   Map<String,Object> row=new LinkedHashMap<>();row.put("runner",cls.getName());
   row.put("bbA",av.value());row.put("bbB",bv.value());
   row.put("bbA_owner",a.getDeclaringClass().getName());row.put("bbB_owner",b.getDeclaringClass().getName());
   row.put("literal_constants_verified",av.kind().equals("literal")&&bv.kind().equals("literal"));
   row.put("static_ownership_verified",proven);row.put("prototype_clone_verified",proven);
   row.put("bbA_proof",av.kind());row.put("bbB_proof",bv.kind());
   row.put("bbA_source",av.source());row.put("bbB_source",bv.source());
   if(rows.put(Integer.toString(entry.d()),row)!=null)throw new IllegalStateException("Duplicate registry entry");
  }
  Map<String,Object> out=new LinkedHashMap<>();
  out.put("source","Installed eVi registry; literal, transparent-super and immutable constructor configuration bytecode proofs; native prototype/clone parity; null requires definition/runtime authority");
  out.put("effects",rows);out.put("static_pairs_verified",verified);out.put("prototype_clone_pairs_verified",clones);
  Files.writeString(Path.of(args[0]),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(out));
  System.out.println("Exported "+rows.size()+" prototype owners; "+verified+" static pairs verified; "+(rows.size()-verified)+" unresolved");
  System.exit(0);
 }
}
