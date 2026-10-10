import com.google.gson.Gson;
import com.jogamp.opengl.GLAutoDrawable;
import com.jogamp.opengl.GL;
import com.sun.net.httpserver.HttpServer;
import io.netty.buffer.ByteBuf;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.Channel;
import java.util.concurrent.ConcurrentHashMap;
import java.awt.Component;
import java.awt.Container;
import java.awt.Frame;
import java.awt.event.MouseEvent;
import java.awt.event.InputEvent;
import java.awt.event.KeyEvent;
import java.awt.event.FocusEvent;
import java.awt.KeyboardFocusManager;
import java.awt.image.BufferedImage;
import java.io.BufferedWriter;
import java.io.ByteArrayOutputStream;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.net.InetSocketAddress;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.ProtectionDomain;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;
import javax.imageio.ImageIO;
import javax.swing.SwingUtilities;
import jdk.internal.org.objectweb.asm.ClassReader;
import jdk.internal.org.objectweb.asm.ClassVisitor;
import jdk.internal.org.objectweb.asm.ClassWriter;
import jdk.internal.org.objectweb.asm.MethodVisitor;
import jdk.internal.org.objectweb.asm.Opcodes;

/** Records each Netty pipeline boundary without changing buffers or forwarding. */
public final class CaptureAgent {
    private static final Gson JSON = new Gson();
 static Object call(Object obj,String name,Object...args)throws Exception {
  Class<?> c=obj instanceof Class?(Class<?>)obj:obj.getClass();
  for(Class<?> t=c;t!=null;t=t.getSuperclass())for(java.lang.reflect.Method m:t.getDeclaredMethods())if(m.getName().equals(name)&&m.getParameterCount()==args.length){m.setAccessible(true);try{return m.invoke(obj instanceof Class?null:obj,args);}catch(IllegalArgumentException e){}}
  throw new NoSuchMethodException(name);
 }
 static Object field(Object obj,String name)throws Exception {
  for(Class<?> t=obj instanceof Class?(Class<?>)obj:obj.getClass();t!=null;t=t.getSuperclass())try{java.lang.reflect.Field f=t.getDeclaredField(name);f.setAccessible(true);return f.get(obj instanceof Class?null:obj);}catch(NoSuchFieldException e){}
  throw new NoSuchFieldException(name);
 }

 private static Map<String,Object> equipmentSheetDiagnostic(Object sheet) throws Exception {
  Map<String,Object> out=new LinkedHashMap<>();
  if(sheet==null){out.put("present",false);return out;}
  out.put("present",true);out.put("identity",System.identityHashCode(sheet));
  out.put("level",call(sheet,"cmZ"));
  Map<?,?> slots=(Map<?,?>)call(sheet,"geO");
  Map<String,Object> values=new LinkedHashMap<>();
  for(Map.Entry<?,?> entry:slots.entrySet())values.put(String.valueOf(call(entry.getKey(),"aKg")),entry.getValue());
  out.put("slots",values);return out;
 }

 private static Map<String,Object> equipmentDiagnostic() {
  Map<String,Object> out=new LinkedHashMap<>();out.put("time",java.time.Instant.now().toString());
  try {
   Object player=call(call(Class.forName("aTx"),"cWt"),"cWu");
   if(player==null){out.put("player_present",false);return out;}
   long id=((Number)call(player,"Sn")).longValue();out.put("actor_id",id);
   Object metadata=call(player,"drq");
   for(String key:new String[]{"fHn","fHo","wM","wR"})out.put("build."+key,call(metadata,key));
   out.put("active_sheet",equipmentSheetDiagnostic(call(player,"dqw")));
   for(int index=0;index<3;index++)out.put("owned_sheet"+index,equipmentSheetDiagnostic(call(player,"Dj",index)));
   Object inventory=call(field(Class.forName("bIM"),"kel"),"tT",id);
   Map<String,Object> items=new LinkedHashMap<>();
   if(inventory!=null){for(Map.Entry<?,?> entry:((Map<?,?>)call(inventory,"giz")).entrySet()){
    Object item=entry.getValue();Map<String,Object> value=new LinkedHashMap<>();
    value.put("reference",call(item,"aZY"));value.put("quantity",call(item,"bfh"));items.put(String.valueOf(entry.getKey()),value);
   }}out.put("owned_items",items);
   Object dialog=call(Class.forName("dbU"),"fdS");out.put("dialog_open",call(Class.forName("dbU"),"fay"));
   out.put("dialog.omt",field(dialog,"omt"));out.put("dialog.omz",field(dialog,"omz"));
   Object clone=field(dialog,"omy");
   if(clone!=null)out.put("dialog_sheet",equipmentSheetDiagnostic(call(field(clone,"jGT"),"dqw")));
  }catch(Throwable error){out.put("error",error.toString());}
  return out;
 }

 private static Map<String,Object> movementDiagnostic() {
  Map<String,Object> out=new LinkedHashMap<>();out.put("time",Instant.now().toString());
  try {
   Object player=call(call(Class.forName("aTx"),"cWt"),"cWu");
   if(player==null){out.put("status","not_loaded");return out;}
   out.put("actor_id",call(player,"Sn"));out.put("name",call(player,"getName"));
   out.put("position",List.of(call(player,"getWorldX"),call(player,"getWorldY"),call(player,"getAltitude")));
   Object movement=call(player,"dhw");
   out.put("movement_class",movement.getClass().getName());
   for(String key:new String[]{"cjs","cjt","cju","cjv","cjz","cjA","hPu"})
    try{out.put(key,field(movement,key));}catch(Throwable error){out.put(key+"_error",error.toString());}
   for(String key:new String[]{"cjr","cjx","cjB","cjC","hPv","hPw"}) {
    try {
     Object value=field(movement,key);Map<String,Object> row=new LinkedHashMap<>();
     row.put("present",value!=null);
     if(value!=null){row.put("class",value.getClass().getName());
      if(key.equals("cjr"))row.put("points",call(value,"bDT"));
      if(key.equals("hPv")||key.equals("hPw"))row.put("steps",call(value,"bWv"));
     }
     out.put(key,row);
    }catch(Throwable error){out.put(key+"_error",error.toString());}
   }
   out.put("native_mode",call(movement,"bvy"));
   out.put("idle_fallback",NativeMovementStop.diagnostic());
   for(String animationMethod:new String[]{"bkG","bpT","bvM"})
    try{out.put(animationMethod,call(movement,animationMethod));}
    catch(Throwable error){out.put(animationMethod+"_error",error.toString());}
   java.util.Collection<?> listeners=(java.util.Collection<?>)field(movement,"cjl");
   out.put("listener_count",listeners.size());List<Map<String,Object>> rows=new ArrayList<>();
   for(Object listener:listeners) {
    if(rows.size()==16)break;
    Map<String,Object> row=new LinkedHashMap<>();row.put("class",listener.getClass().getName());
    if(listener.getClass().getName().equals("cWt"))try {
     Object interaction=field(listener,"nGb");row.put("interaction_present",interaction!=null);
     Object target=interaction==null?null:call(interaction,"dTN");
     row.put("interaction_target_present",target!=null);
     if(target!=null)row.put("interaction_target_id",call(target,"Xi"));
    }catch(Throwable error){row.put("interaction_error",error.toString());}
    rows.add(row);
   }
   out.put("path_end_listeners",rows);out.put("listeners_truncated",listeners.size()>16);
  }catch(Throwable error){out.put("error",error.toString());}
  return out;
 }

 private static Map<String,Object> combatDiagnostic() {
  Map<String,Object> out=new LinkedHashMap<>();out.put("time",java.time.Instant.now().toString());
  try {
   Object ownPlayer=call(call(Class.forName("aTx"),"cWt"),"cWu");
   out.put("own_player_present",ownPlayer!=null);
   if(ownPlayer!=null) {
    out.put("own_player_id",String.valueOf(call(ownPlayer,"Sn")));
    out.put("own_player_fight",String.valueOf(call(ownPlayer,"doI")));
   }
  }catch(Throwable error){out.put("own_player_error",error.toString());}
  try {
   Object dbe=call(Class.forName("dbe"),"fcF"),dba=call(Class.forName("dba"),"fcm");
   for(String key:new String[]{"NO","cEV","okd","oke","okf"})out.put("dbe."+key,field(dbe,key));
   for(String key:new String[]{"fcs","fct","fcA"})out.put("dba."+key,call(dba,key));
   for(String key:new String[]{"bVK","bVL","ojT"})out.put("dba."+key,field(dba,key));
   Object target=call(dba,"fcn");out.put("target",String.valueOf(target));
   Object route=field(dbe,"okg");out.put("route",String.valueOf(route));if(route!=null)out.put("path_points",call(route,"bDT"));
   Object fight=call(dba,"cXY"),timeline=call(fight,"dLW"),actor=call(timeline,"dNG");
   out.put("fight_phase",String.valueOf(call(fight,"dLv")));
   Object ownPlayer=call(call(Class.forName("aTx"),"cWt"),"cWu");
   out.put("own_player_fight",String.valueOf(call(ownPlayer,"doI")));
   Object ownFighter=call(fight,"rj",((Number)call(ownPlayer,"Sn")).longValue());
   Map<String,Object> resources=new LinkedHashMap<>();
   if(ownFighter!=null){
    resources.put("id",call(ownFighter,"Sn"));
    for(String stat:new String[]{"sgC","shQ","shL","shH"}){
     Object definition=field(Class.forName("ffw"),stat);
     resources.put(stat+".id",call(definition,"aKg"));
     resources.put(stat+".current",call(ownFighter,"c",definition));
     resources.put(stat+".maximum",call(call(ownFighter,"e",definition),"aYU"));
    }
   }
   out.put("own_fighter_resources",resources);
   out.put("actor_fight",String.valueOf(call(actor,"doI")));
   out.put("actor_id",call(actor,"Xi"));out.put("actor_owned",call(actor,"doz"));out.put("actor_position",String.valueOf(call(actor,"baM")));
   out.put("actor_mp",call(actor,"c",field(Class.forName("ffw"),"sgE")));
  }catch(Throwable t){out.put("error",t.toString());}
  return out;
 }

 private static Map<String,Object> interactiveRegistryDiagnostic(List<Long> ids) {
  Map<String,Object> out=new LinkedHashMap<>();out.put("time",Instant.now().toString());
  try {
   Object game=call(Class.forName("aTx"),"cWt");
   if(game==null||call(game,"cWv")==null){out.put("status","not_loaded");return out;}
   Object rawRegistry=call(Class.forName("bEC"),"dVG");
   Object scene=call(Class.forName("cdE"),"exN");
   List<?> loaded=(List<?>)call(scene,"exP");
   Map<Long,Object> rendered=new LinkedHashMap<>();
   int sceneObjectCount=0;
   for(Object candidate:loaded) {
    sceneObjectCount++;
    if(Class.forName("bEG").isInstance(candidate))
     rendered.put(((Number)call(candidate,"Sn")).longValue(),candidate);
   }
   out.put("scene_object_count",sceneObjectCount);
   out.put("scene_interactive_count",rendered.size());
   try {
    Object screen=call(Class.forName("cdG"),"exW"),meta=call(screen,"exX");
    out.put("map_id",meta==null?null:field(meta,"cgb"));
    out.put("world_map_id",field(screen,"bqh"));
   } catch(Throwable error) {out.put("map_error",error.toString());}
   List<Map<String,Object>> rows=new ArrayList<>();
   for(long id:ids) {
    Map<String,Object> row=new LinkedHashMap<>();row.put("id",id);
    Object raw=call(rawRegistry,"ds",id);row.put("raw_exists",raw!=null);
    if(raw!=null) {
     short type=((Number)field(raw,"bkI")).shortValue();byte[] payload=(byte[])field(raw,"bkJ");
     row.put("raw_type_id",type);row.put("raw_payload_bytes",payload.length);
     try {Object definition=call(Class.forName("bEE"),"cb",type);row.put("raw_type",definition==null?null:call(definition,"aYh"));}
     catch(Throwable ignored){}
    }
    Object object=rendered.get(id);row.put("rendered_exists",object!=null);
    if(object!=null) {
     row.put("class",object.getClass().getName());row.put("name",call(object,"getName"));
     Object x=call(object,"getWorldX"),y=call(object,"getWorldY"),z=call(object,"getAltitude");
     row.put("x",x);row.put("y",y);row.put("z",z);
     row.put("visible",call(object,"isVisible"));row.put("usable",call(object,"isUsable"));
     row.put("selectable",call(object,"isSelectable"));row.put("state_short",call(object,"dVL"));
     row.put("state_int",call(object,"dVM"));row.put("state",String.valueOf(call(object,"dVN")));
     short type=((Number)call(object,"bem")).shortValue();row.put("native_type_id",type);
     try {Object definition=call(Class.forName("bEE"),"cb",type);row.put("native_type",definition==null?null:call(definition,"aYh"));}
     catch(Throwable ignored){}
     List<Map<String,Object>> actions=new ArrayList<>();
     for(Object action:(Object[])call(object,"bee")) {
      Map<String,Object> a=new LinkedHashMap<>();a.put("id",call(action,"beb"));
      a.put("name",call(action,"aYh"));a.put("label",call(action,"aYi"));actions.add(a);
     }
     row.put("actions",actions);
     try {
      int cellX=(int)Math.floor(((Number)x).doubleValue()),cellY=(int)Math.floor(((Number)y).doubleValue());
      for(Object partition:(List<?>)call(scene,"ble")) {
       if(Boolean.TRUE.equals(call(partition,"aF",cellX,cellY))) {
        Map<String,Object> chunk=new LinkedHashMap<>();
        chunk.put("x",call(partition,"getX"));chunk.put("y",call(partition,"getY"));
        chunk.put("width",call(partition,"getWidth"));chunk.put("height",call(partition,"getHeight"));
        row.put("current_loaded_chunk",chunk);break;
       }
      }
     } catch(Throwable error) {row.put("chunk_error",error.toString());}
    }
    rows.add(row);
   }
   out.put("objects",rows);
  } catch(Throwable error) {
   out.put("status","error");
   List<String> causes=new ArrayList<>();
   Throwable current=error;
   for(int i=0;current!=null&&i<8;i++,current=current.getCause()) {
    String message=current.getMessage();
    if(message!=null&&message.length()>256)message=message.substring(0,256);
    causes.add(current.getClass().getName()+(message==null?"":": "+message));
   }
   out.put("cause_chain",causes);
  }
  return out;
 }

    private static final AtomicLong SEQUENCE = new AtomicLong();
    private static BufferedWriter output;
    private static Path sessionDir;
    private static boolean errorReported;

    private static synchronized void append(Map<String, Object> event) throws Exception {
        event.put("seq", SEQUENCE.incrementAndGet());
        event.put("time", Instant.now().toString());
        event.put("monotonic_ns", System.nanoTime());
        output.write(JSON.toJson(event));
        output.newLine();
        output.flush();
    }

    public static void observe(Object context, Object message, String direction) {
        try {
            ChannelHandlerContext ctx = (ChannelHandlerContext) context;
            Map<String, Object> event = new LinkedHashMap<>();
            event.put("event", "message");
            event.put("direction", direction);
            event.put("channel", ctx.channel().id().asLongText());
            event.put("local", String.valueOf(ctx.channel().localAddress()));
            event.put("remote", String.valueOf(ctx.channel().remoteAddress()));
            event.put("stage", ctx.name());
            event.put("handler", ctx.handler().getClass().getName());
            event.put("pipeline", ctx.pipeline().names());
            event.put("class", message.getClass().getName());
            if (message instanceof ByteBuf buffer) {
                byte[] bytes = new byte[buffer.readableBytes()];
                buffer.getBytes(buffer.readerIndex(), bytes);
                event.put("bytes", bytes.length);
                event.put("payload_base64", Base64.getEncoder().encodeToString(bytes));
            }
            // Object payloads are deliberately not reflected or converted to strings.
            append(event);
        } catch (Throwable error) {
            if (!errorReported) {
                errorReported = true;
                System.err.println("CaptureAgent recording error: " + error.getClass().getSimpleName());
            }
        }
    }

    private static final ConcurrentHashMap<String, String> firstClose = new ConcurrentHashMap<>();

    public static void observeLifecycle(Object context, String kind, Object failure) {
        try {
            ChannelHandlerContext ctx = context instanceof ChannelHandlerContext ? (ChannelHandlerContext) context : null;
            Channel channel = ctx != null ? ctx.channel() : (Channel) field(context, "this$0");
            LinkedHashMap<String, Object> event = new LinkedHashMap<>();
            event.put("event", "channel_lifecycle");
            event.put("kind", kind);
            String channelId = channel.id().asLongText();
            event.put("channel", channelId);
            event.put("local", String.valueOf(channel.localAddress()));
            event.put("remote", String.valueOf(channel.remoteAddress()));
            event.put("stage", ctx != null ? ctx.name() : context.getClass().getName());
            event.put("thread", Thread.currentThread().getName());
            if (kind.contains("close") || kind.contains("disconnect")) {
                String previous = firstClose.putIfAbsent(channelId, kind);
                event.put("first_close", previous == null);
                event.put("first_close_kind", previous == null ? kind : previous);
            }
            if (failure instanceof Throwable error) event.put("exception_type", error.getClass().getName());
            // No exception messages, object strings, payloads or frame locals.
            List<String> frames = new ArrayList<>();
            for (StackTraceElement frame : Thread.currentThread().getStackTrace()) {
                if (frames.size() == 40) break;
                frames.add(frame.getClassName() + "." + frame.getMethodName() + ":" + frame.getLineNumber());
            }
            event.put("stack", frames);
            append(event);
        } catch (Throwable ignored) {
            // Diagnostic recording must never alter channel behavior.
        }
    }

    static byte[] spectatorTerminalAck(byte[] data) {
        ClassReader reader = new ClassReader(data);
        ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
        int[] patched = {0};
        reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
            @Override
            public MethodVisitor visitMethod(int access, String method, String desc, String signature, String[] exceptions) {
                MethodVisitor target = super.visitMethod(access, method, desc, signature, exceptions);
                if (!method.equals("cbj") || !desc.equals("()V")) return target;
                return new MethodVisitor(Opcodes.ASM8, target) {
                    @Override
                    public void visitFieldInsn(int opcode, String owner, String field, String descriptor) {
                        if (opcode == Opcodes.GETFIELD && owner.equals("aUH") && field.equals("huP") && descriptor.equals("Z")) {
                            // cbj runs after native terminal cleanup. Preserve its
                            // coQ packet and loss flag, but acknowledge observers
                            // too so the server can safely clear retained NPCs.
                            // Keep the original receiver/result stack shape.
                            super.visitInsn(Opcodes.POP);
                            super.visitInsn(Opcodes.ICONST_0);
                            patched[0]++;
                        } else super.visitFieldInsn(opcode, owner, field, descriptor);
                    }
                };
            }
        }, 0);
        if (patched[0] != 1) throw new IllegalStateException("Unexpected native spectator terminal ACK boundary");
        return writer.toByteArray();
    }

    public static void premain(String directory, Instrumentation instrumentation) throws Exception {
        Path base = Path.of(directory);
        Files.createDirectories(base);
        sessionDir = base.resolve(Instant.now().toString().replace(':', '-') + "-" + UUID.randomUUID().toString().substring(0, 8));
        Files.createDirectory(sessionDir, PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")));
        output = Files.newBufferedWriter(sessionDir.resolve("events.jsonl"));
        append(new LinkedHashMap<>(Map.of("event", "capture_start", "lifecycle_version", 2, "scope", "Netty pipeline bytes and message classes; includes repeated stages and TLS ciphertext/plaintext")));
        instrumentation.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader, String name, Class<?> clazz, ProtectionDomain domain, byte[] data) {
                if ("aUH".equals(name)) return spectatorTerminalAck(data);
                if ("fnR".equals(name)) {
                    ClassReader reader = new ClassReader(data);
                    ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
                    reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
                        @Override
                        public MethodVisitor visitMethod(int access, String method, String desc, String signature, String[] exceptions) {
                            MethodVisitor target = super.visitMethod(access, method, desc, signature, exceptions);
                            boolean snapshot = method.equals("f") && desc.equals("(LfvH;)V");
                            boolean hydrated = method.equals("a") && desc.equals("(LwS;)V");
                            if (!snapshot && !hydrated) return target;
                            return new MethodVisitor(Opcodes.ASM8, target) {
                                @Override
                                public void visitCode() {
                                    super.visitCode();
                                    if (snapshot) {
                                        super.visitVarInsn(Opcodes.ALOAD, 0);
                                        super.visitVarInsn(Opcodes.ALOAD, 1);
                                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "NativePetStateRefresh", "reconcile", "(LfnR;LfvH;)LfvH;", false);
                                        super.visitVarInsn(Opcodes.ASTORE, 1);
                                    }
                                }
                                @Override
                                public void visitFieldInsn(int opcode, String owner, String field, String descriptor) {
                                    if (hydrated && opcode == Opcodes.PUTFIELD && owner.equals("fnR") && field.equals("kuu") && descriptor.equals("LfvH;")) {
                                        // Preserve the original receiver/value stack shape and stack maps.
                                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "NativePetStateRefresh", "assignHydrated", "(LfnR;LfvH;)V", false);
                                    } else super.visitFieldInsn(opcode, owner, field, descriptor);
                                }
                            };
                        }
                    }, 0);
                    return writer.toByteArray();
                }
                if ("bPO".equals(name)) {
                    ClassReader reader = new ClassReader(data);
                    ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
                    reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
                        @Override
                        public MethodVisitor visitMethod(int access, String method, String desc, String signature, String[] exceptions) {
                            MethodVisitor target = super.visitMethod(access, method, desc, signature, exceptions);
                            if (!method.equals("eH") || !desc.equals("(Ljava/lang/String;)Ljava/lang/Object;")) return target;
                            return new MethodVisitor(Opcodes.ASM8, target) {
                                @Override
                                public void visitMethodInsn(int opcode, String owner, String called, String descriptor, boolean iface) {
                                    if (opcode == Opcodes.INVOKEVIRTUAL && owner.equals("buH") && called.equals("a") && descriptor.equals("(LeGj;LfyG;LaBn;Z)LfyJ;")) {
                                        // Consume exactly the original receiver/arguments; preserve stack maps.
                                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "NativeSpellPreflight", "query", "(LbuH;LeGj;LfyG;LaBn;Z)LfyJ;", false);
                                    } else {
                                        super.visitMethodInsn(opcode, owner, called, descriptor, iface);
                                    }
                                }
                            };
                        }
                    }, 0);
                    return writer.toByteArray();
                }
                if ("adf".equals(name)) {
                    ClassReader reader = new ClassReader(data);
                    ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
                    reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
                        @Override
                        public MethodVisitor visitMethod(int access, String method, String desc, String signature, String[] exceptions) {
                            MethodVisitor target = super.visitMethod(access, method, desc, signature, exceptions);
                            if (!method.equals("b") || !desc.equals("(LacX;)V")) return target;
                            return new MethodVisitor(Opcodes.ASM8, target) {
                                @Override
                                public void visitMethodInsn(int opcode, String owner, String called, String descriptor, boolean iface) {
                                    if (opcode == Opcodes.INVOKEINTERFACE && owner.equals("acX") && called.equals("eg") && descriptor.equals("(Ljava/lang/String;)Z")) {
                                        // Identical operand consumption; no added local loads or frames.
                                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "NativeMovementStop", "finish", "(LacX;Ljava/lang/String;)Z", false);
                                    } else super.visitMethodInsn(opcode, owner, called, descriptor, iface);
                                }
                            };
                        }
                    }, 0);
                    return writer.toByteArray();
                }
                boolean unsafe = "io/netty/channel/AbstractChannel$AbstractUnsafe".equals(name);
                if (!unsafe && !"io/netty/channel/AbstractChannelHandlerContext".equals(name)) return null;
                ClassReader reader = new ClassReader(data);
                ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
                reader.accept(new ClassVisitor(Opcodes.ASM8, writer) {
                    @Override
                    public MethodVisitor visitMethod(int access, String method, String desc, String signature, String[] exceptions) {
                        MethodVisitor target = super.visitMethod(access, method, desc, signature, exceptions);
                        boolean incoming = method.equals("invokeChannelRead") && desc.equals("(Ljava/lang/Object;)V");
                        boolean outgoing = method.equals("invokeWrite0") && desc.equals("(Ljava/lang/Object;Lio/netty/channel/ChannelPromise;)V");
                        String lifecycle = null;
                        if (method.equals("invokeClose") && desc.equals("(Lio/netty/channel/ChannelPromise;)V")) lifecycle = "close_requested";
                        if (method.equals("invokeDisconnect") && desc.equals("(Lio/netty/channel/ChannelPromise;)V")) lifecycle = "disconnect_requested";
                        if (method.equals("invokeChannelInactive") && desc.equals("()V")) lifecycle = "inactive";
                        if (method.equals("invokeExceptionCaught") && desc.equals("(Ljava/lang/Throwable;)V")) lifecycle = "exception";
                        if (unsafe) {
                            lifecycle = null;
                            if (method.equals("close") && desc.startsWith("(Lio/netty/channel/ChannelPromise;")) lifecycle = "unsafe_close";
                            if (method.equals("doClose0") && desc.equals("(Lio/netty/channel/ChannelPromise;)V")) lifecycle = "transport_close";
                            if (method.equals("closeForcibly") && desc.equals("()V")) lifecycle = "unsafe_close_forcibly";
                            if (method.equals("disconnect") && desc.equals("(Lio/netty/channel/ChannelPromise;)V")) lifecycle = "unsafe_disconnect";
                        }
                        if (lifecycle != null) {
                            final String kind = lifecycle;
                            return new MethodVisitor(Opcodes.ASM8, target) {
                                @Override public void visitCode() {
                                    super.visitCode();
                                    visitVarInsn(Opcodes.ALOAD, 0);
                                    visitLdcInsn(kind);
                                    if (kind.equals("exception")) visitVarInsn(Opcodes.ALOAD, 1);
                                    else visitInsn(Opcodes.ACONST_NULL);
                                    visitMethodInsn(Opcodes.INVOKESTATIC, "CaptureAgent", "observeLifecycle", "(Ljava/lang/Object;Ljava/lang/String;Ljava/lang/Object;)V", false);
                                }
                            };
                        }
                        if (!incoming && !outgoing) return target;
                        return new MethodVisitor(Opcodes.ASM8, target) {
                            @Override public void visitCode() {
                                super.visitCode();
                                visitVarInsn(Opcodes.ALOAD, 0);
                                visitVarInsn(Opcodes.ALOAD, 1);
                                visitLdcInsn(incoming ? "in" : "out");
                                visitMethodInsn(Opcodes.INVOKESTATIC, "CaptureAgent", "observe", "(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/String;)V", false);
                            }
                        };
                    }
                }, 0);
                try { append(new LinkedHashMap<>(Map.of("event", "hooks_installed", "class", name))); }
                catch (Exception error) { throw new IllegalStateException(error); }
                return writer.toByteArray();
            }
        });
        startInspector();
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try { append(new LinkedHashMap<>(Map.of("event", "capture_stop"))); output.close(); }
            catch (Exception ignored) {}
        }));
        System.out.println("CaptureAgent recording from JVM start to " + sessionDir);
    }

    private static void collect(Component component, List<Map<String, Object>> nodes) {
        nodes.add(Map.of("class", component.getClass().getName(), "width", component.getWidth(),
            "height", component.getHeight(), "visible", component.isVisible()));
        if (component instanceof Container container) {
            for (Component child : container.getComponents()) collect(child, nodes);
        }
    }

    private static GLAutoDrawable drawable(Component component) {
        if (component instanceof GLAutoDrawable gl && component.isShowing()) return gl;
        if (component instanceof Container container) {
            for (Component child : container.getComponents()) {
                GLAutoDrawable candidate = drawable(child);
                if (candidate != null) return candidate;
            }
        }
        return null;
    }

    private static void dragCanvas(int x, int y, int endX, int endY) throws Exception {
        final Component[] found = new Component[1];
        SwingUtilities.invokeAndWait(() -> {
            for (Frame f : Frame.getFrames()) if (drawable(f) instanceof Component c && c.isShowing()) {
                for (int[] p : new int[][]{{x,y},{endX,endY}})
                    if (p[0]<0 || p[1]<0 || p[0]>=c.getWidth() || p[1]>=c.getHeight()) throw new IllegalArgumentException("Drag outside canvas");
                found[0]=c; c.requestFocusInWindow();
                c.dispatchEvent(new MouseEvent(c,MouseEvent.MOUSE_MOVED,System.currentTimeMillis(),0,x,y,0,false,0)); return;
            }
            throw new IllegalStateException("No visible canvas");
        });
        Thread.sleep(150);
        Component c=found[0];
        SwingUtilities.invokeAndWait(() -> c.dispatchEvent(new MouseEvent(c,MouseEvent.MOUSE_PRESSED,System.currentTimeMillis(),InputEvent.BUTTON1_DOWN_MASK,x,y,1,false,1)));
        Thread.sleep(100);
        for (int step=1; step<=12; step++) {
            final int px=x+(endX-x)*step/12, py=y+(endY-y)*step/12;
            SwingUtilities.invokeAndWait(() -> c.dispatchEvent(new MouseEvent(c,MouseEvent.MOUSE_DRAGGED,System.currentTimeMillis(),InputEvent.BUTTON1_DOWN_MASK,px,py,0,false,0)));
            Thread.sleep(35);
        }
        Thread.sleep(150);
        SwingUtilities.invokeAndWait(() -> c.dispatchEvent(new MouseEvent(c,MouseEvent.MOUSE_RELEASED,System.currentTimeMillis(),0,endX,endY,1,false,1)));
    }

    private static void clickCanvas(int x, int y) throws Exception {
        clickCanvas(x, y, MouseEvent.BUTTON1);
    }

    private static void clickCanvas(int x, int y, int button) throws Exception {
        clickCanvas(x,y,button,1);
    }

    private static void clickCanvas(int x, int y, int button, int count) throws Exception {
        if (count < 1 || count > 2) throw new IllegalArgumentException("Invalid click count");
        if (button != MouseEvent.BUTTON1 && button != MouseEvent.BUTTON3) throw new IllegalArgumentException("Unsupported mouse button");
        SwingUtilities.invokeAndWait(() -> {
            for (Frame frame : Frame.getFrames()) {
                if (drawable(frame) instanceof Component canvas && canvas.isShowing()) {
                    if (x < 0 || y < 0 || x >= canvas.getWidth() || y >= canvas.getHeight())
                        throw new IllegalArgumentException("Click outside canvas");
                    canvas.requestFocusInWindow();
                    canvas.dispatchEvent(new MouseEvent(canvas, MouseEvent.MOUSE_MOVED, System.currentTimeMillis(), 0, x, y, 0, false, MouseEvent.NOBUTTON));
                    return;
                }
            }
            throw new IllegalStateException("No visible canvas");
        });
        Thread.sleep(150); // Allow picking/path refresh on the render thread before release.
        SwingUtilities.invokeAndWait(() -> {
            for (Frame frame : Frame.getFrames()) {
                GLAutoDrawable gl = drawable(frame);
                if (!(gl instanceof Component canvas)) continue;
                if (x < 0 || y < 0 || x >= canvas.getWidth() || y >= canvas.getHeight()) {
                    throw new IllegalArgumentException("Click outside canvas");
                }
                canvas.requestFocusInWindow();
                long now = System.currentTimeMillis();
                int mask = button == MouseEvent.BUTTON1 ? InputEvent.BUTTON1_DOWN_MASK : InputEvent.BUTTON3_DOWN_MASK;
                canvas.dispatchEvent(new MouseEvent(canvas, MouseEvent.MOUSE_PRESSED, now, mask, x, y, count, false, button));

                return;
            }
            throw new IllegalStateException("No visible canvas");
        });
        Thread.sleep(150); // Keep the button pressed across render frames.
        SwingUtilities.invokeAndWait(() -> {
            for (Frame frame : Frame.getFrames()) {
                if (drawable(frame) instanceof Component canvas && canvas.isShowing()) {
                    long now = System.currentTimeMillis();
                    canvas.dispatchEvent(new MouseEvent(canvas, MouseEvent.MOUSE_RELEASED, now, 0, x, y, count, button == MouseEvent.BUTTON3, button));
                    canvas.dispatchEvent(new MouseEvent(canvas, MouseEvent.MOUSE_CLICKED, now + 1, 0, x, y, count, false, button));
                    return;
                }
            }
            throw new IllegalStateException("No visible canvas");
        });
    }

    private static byte[] screenshot() throws Exception {
        GLAutoDrawable[] found = new GLAutoDrawable[1];
        SwingUtilities.invokeAndWait(() -> {
            for (Frame frame : Frame.getFrames()) {
                GLAutoDrawable gl = drawable(frame);
                if (gl != null) { found[0] = gl; break; }
            }
        });
        if (found[0] == null) throw new IllegalStateException("No GL drawable visible");
        BufferedImage[] result = new BufferedImage[1];
        found[0].invoke(true, gl -> {
            int width = gl.getSurfaceWidth(), height = gl.getSurfaceHeight();
            ByteBuffer pixels = ByteBuffer.allocateDirect(width * height * 4);
            gl.getGL().glReadPixels(0, 0, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels);
            BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB);
            for (int y = 0; y < height; y++) for (int x = 0; x < width; x++) {
                int offset = ((height - 1 - y) * width + x) * 4;
                int argb = ((pixels.get(offset + 3) & 255) << 24) | ((pixels.get(offset) & 255) << 16)
                    | ((pixels.get(offset + 1) & 255) << 8) | (pixels.get(offset + 2) & 255);
                image.setRGB(x, y, argb);
            }
            result[0] = image;
            return true;
        });
        if (result[0] == null) throw new IllegalStateException("GL capture did not run");
        ByteArrayOutputStream stream = new ByteArrayOutputStream();
        ImageIO.write(result[0], "png", stream);
        return stream.toByteArray();
    }

    private static void typeCanvas(String text, boolean submit, int modifiers) throws Exception {
        Component[] found = new Component[1];
        SwingUtilities.invokeAndWait(() -> {
            for (Frame frame : Frame.getFrames()) {
                if (drawable(frame) instanceof Component canvas) {
                    frame.toFront();
                    frame.requestFocus();
                    canvas.requestFocusInWindow();
                    canvas.dispatchEvent(new FocusEvent(canvas, FocusEvent.FOCUS_GAINED));
                    found[0] = canvas;
                    break;
                }
            }
        });
        Thread.sleep(200); // Native focus events arrive after the AWT request.
        Component canvas = found[0];
        if (canvas == null) throw new IllegalStateException("No visible canvas");
        String keys = text + (submit ? "\n" : "");
        for (char ch : keys.toCharArray()) {
            int code = ch == '\n' ? KeyEvent.VK_ENTER : KeyEvent.getExtendedKeyCodeForChar(ch);
            SwingUtilities.invokeAndWait(() -> {
                KeyboardFocusManager keyboard = KeyboardFocusManager.getCurrentKeyboardFocusManager();
                long now = System.currentTimeMillis();
                keyboard.redispatchEvent(canvas, new KeyEvent(canvas, KeyEvent.KEY_PRESSED, now, modifiers, code, ch));
                if (ch != '\n') keyboard.redispatchEvent(canvas, new KeyEvent(canvas, KeyEvent.KEY_TYPED, now, modifiers, KeyEvent.VK_UNDEFINED, ch));
            });
            Thread.sleep(35); // Let the game process the pressed key before release.
            SwingUtilities.invokeAndWait(() -> KeyboardFocusManager.getCurrentKeyboardFocusManager().redispatchEvent(
                canvas, new KeyEvent(canvas, KeyEvent.KEY_RELEASED, System.currentTimeMillis(), modifiers, code, ch)));
            Thread.sleep(35);
        }
    }

    private static void startInspector() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        String secret = UUID.randomUUID().toString();
        Path config = sessionDir.getParent().getParent().resolve("inspector.json");
        if (!Files.exists(config)) Files.createFile(config,
            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")));
        Files.writeString(config, JSON.toJson(Map.of("port", server.getAddress().getPort(), "secret", secret,
            "capture", sessionDir.toString())));
        server.createContext("/", exchange -> {
            if (!secret.equals(exchange.getRequestHeaders().getFirst("X-Inspector-Key"))) {
                exchange.sendResponseHeaders(403, -1); exchange.close(); return;
            }
            try {
                byte[] response;
                switch (exchange.getRequestURI().getPath()) {
                    case "/focus-chat" -> {
                        Map<String, Object> state = new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> {
                            try {
                                Object chat = Class.forName("cZy").getMethod("eZo").invoke(null);
                                Object dialog = chat.getClass().getMethod("eZp").invoke(chat);
                                Object map = dialog.getClass().getMethod("getElementMap").invoke(dialog);
                                Object input = map.getClass().getMethod("wo", String.class).invoke(map, "textEditorRenderableContainer.chatInput");
                                if (input == null) throw new IllegalStateException("Chat input is not present");
                                Class<?> focusClass = Class.forName("fQd");
                                Object manager = focusClass.getMethod("gOg").invoke(null);
                                focusClass.getMethod("t", Class.forName("fMZ")).invoke(manager, input);
                                state.put("id", input.getClass().getMethod("getId").invoke(input));
                                state.put("focusable", input.getClass().getMethod("getFocusable").invoke(input));
                                Object active = focusClass.getMethod("gOh").invoke(manager);
                                state.put("active", active == input);
                            } catch (Exception error) { throw new RuntimeException(error); }
                        });
                        response = JSON.toJson(state).getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/type" -> {
                        Map<?, ?> input = JSON.fromJson(new String(exchange.getRequestBody().readNBytes(4096), java.nio.charset.StandardCharsets.UTF_8), Map.class);
                        String text = (String) input.get("text");
                        boolean submit = Boolean.TRUE.equals(input.get("submit"));
                        if (text.length() > 512) throw new IllegalArgumentException("Text too long");
                        int modifiers = Boolean.TRUE.equals(input.get("shift")) ? InputEvent.SHIFT_DOWN_MASK : 0;
                        typeCanvas(text, submit, modifiers);
                        response = "ok".getBytes();
                    }
                    case "/actors" -> {
                        List<Map<String, Object>> actors = new ArrayList<>();
                        SwingUtilities.invokeAndWait(() -> {
                            try {
                                Class<?> managerClass = Class.forName("bio");
                                Object manager = managerClass.getMethod("dpx").invoke(null);
                                java.util.Iterator<?> iterator = (java.util.Iterator<?>) managerClass.getMethod("bak").invoke(manager);
                                while (iterator.hasNext()) {
                                    Object actor = iterator.next();
                                    Map<String, Object> state = new LinkedHashMap<>();
                                    for (String[] pair : new String[][]{{"id", "Sn"}, {"name", "getName"}, {"x", "getWorldX"}, {"y", "getWorldY"}, {"z", "getAltitude"}})
                                        state.put(pair[0], actor.getClass().getMethod(pair[1]).invoke(actor));
                                    actors.add(state);
                                }
                            } catch (Exception error) { throw new RuntimeException(error); }
                        });
                        response = (JSON.toJson(actors) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/actor-registry" -> {
                        Map<?, ?> input = JSON.fromJson(new String(exchange.getRequestBody().readNBytes(4096), java.nio.charset.StandardCharsets.UTF_8), Map.class);
                        Object rawIds = input.get("actor_ids");
                        if (!(rawIds instanceof List<?> ids) || ids.isEmpty() || ids.size() > 16)
                            throw new IllegalArgumentException("actor_ids must contain 1..16 ids");
                        List<Map<String, Object>> actors = new ArrayList<>();
                        SwingUtilities.invokeAndWait(() -> {
                            try {
                                Class<?> managerClass = Class.forName("bio");
                                Object manager = managerClass.getMethod("dpx").invoke(null);
                                java.util.Iterator<?> iterator = (java.util.Iterator<?>) managerClass.getMethod("bak").invoke(manager);
                                java.util.Set<Object> worldActors = java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<>());
                                while (iterator.hasNext()) worldActors.add(iterator.next());
                                for (Object rawId : ids) {
                                    if (!(rawId instanceof String idText))
                                        throw new IllegalArgumentException("actor ids must be decimal strings");
                                    long id = Long.parseLong(idText);
                                    Object actor = managerClass.getMethod("jv", long.class).invoke(manager, id);
                                    Map<String, Object> state = new LinkedHashMap<>();
                                    state.put("id", id);
                                    state.put("found_by_jv", actor != null);
                                    state.put("in_world_actor_list", actor != null && worldActors.contains(actor));
                                    if (actor != null) {
                                        state.put("class", actor.getClass().getName());
                                        for (String[] pair : new String[][]{{"native_id", "Sn"}, {"name", "getName"}, {"x", "getWorldX"}, {"y", "getWorldY"}, {"z", "getAltitude"}})
                                            state.put(pair[0], actor.getClass().getMethod(pair[1]).invoke(actor));
                                        Map<String, Object> graphicState = new LinkedHashMap<>();
                                        try {
                                            Object graphic = call(actor, "dhw");
                                            graphicState.put("present", graphic != null);
                                            if (graphic != null) {
                                                graphicState.put("class", graphic.getClass().getName());
                                                graphicState.put("identity", System.identityHashCode(graphic));
                                                graphicState.put("visible", call(graphic, "isVisible"));
                                                Object scene = call(Class.forName("cdE"), "exN");
                                                Object loaded = call(scene, "exP");
                                                if (loaded instanceof Iterable<?> objects) {
                                                    boolean found = false;
                                                    for (Object object : objects) if (object == graphic) { found = true; break; }
                                                    graphicState.put("in_scene_object_list", found);
                                                }
                                            }
                                            Object model = call(actor, "bwX");
                                            graphicState.put("model_present", model != null);
                                            if (model != null) {
                                                graphicState.put("model_class", model.getClass().getName());
                                                graphicState.put("model_identity", System.identityHashCode(model));
                                            }
                                        } catch (Exception error) {
                                            graphicState.put("error_class", error.getClass().getName());
                                            graphicState.put("error_message", error.getMessage());
                                        }
                                        state.put("graphic", graphicState);
                                    }
                                    actors.add(state);
                                }
                            } catch (Exception error) { throw new RuntimeException(error); }
                        });
                        response = (JSON.toJson(actors) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/native-replay" -> {
                        Path profileRoot = sessionDir.getParent().getParent();
                        if (!profileRoot.getFileName().toString().startsWith("issue16-marker-visual-"))
                            throw new IllegalStateException("Native replay is restricted to issue16 visual test profiles");
                        Map<?, ?> input = JSON.fromJson(new String(exchange.getRequestBody().readNBytes(140000), java.nio.charset.StandardCharsets.UTF_8), Map.class);
                        if (!(input.get("opcode") instanceof Number opcodeValue) || !(input.get("body_base64") instanceof String encoded))
                            throw new IllegalArgumentException("opcode and body_base64 are required");
                        int opcode = opcodeValue.intValue();
                        if (opcode != 12304 && opcode != 12608 && opcode != 13753)
                            throw new IllegalArgumentException("Only native world actor and marker opcodes may be replayed");
                        byte[] packet = Base64.getDecoder().decode(encoded);
                        if (packet.length < 1 || packet.length > 65536)
                            throw new IllegalArgumentException("Invalid native replay body size");
                        Map<String, Object> result = new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> {
                            try {
                                String className = switch (opcode) {
                                    case 12304 -> "ctA";
                                    case 12608 -> "ctE";
                                    default -> "cuY";
                                };
                                Class<?> messageClass = Class.forName(className);
                                Object message = messageClass.getConstructor().newInstance();
                                boolean decoded = (Boolean) call(message, "dp", packet);
                                int decodedOpcode = ((Number) call(message, "d")).intValue();
                                if (!decoded || decodedOpcode != opcode)
                                    throw new IllegalArgumentException("Native packet decoder rejected body");
                                boolean accepted;
                                if (opcode == 13753) {
                                    Class<?> handlerClass = Class.forName("ckM");
                                    var constructor = handlerClass.getDeclaredConstructor();
                                    constructor.setAccessible(true);
                                    Object handler = constructor.newInstance();
                                    accepted = (Boolean) call(handler, "a", message);
                                } else {
                                    Object dispatcher = call(Class.forName("cgN"), "eCA");
                                    accepted = (Boolean) call(dispatcher, "b", message);
                                }
                                result.put("opcode", opcode);
                                result.put("decoded", decoded);
                                result.put("native_handler_accepted", accepted);
                            } catch (Exception error) { throw new RuntimeException(error); }
                        });
                        response = (JSON.toJson(result) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/position" -> {
                        Map<String, Object> position = new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> {
                            try {
                                Object game = Class.forName("aTx").getMethod("cWt").invoke(null);
                                Object player = game.getClass().getMethod("cWv").invoke(game);
                                if (player == null) { position.put("status", "not_loaded"); return; }
                                position.put("time", Instant.now().toString());
                                for (String[] pair : new String[][]{{"name", "getName"}, {"x", "getWorldX"}, {"y", "getWorldY"}, {"z", "getAltitude"}})
                                    position.put(pair[0], player.getClass().getMethod(pair[1]).invoke(player));
                            } catch (Exception error) { throw new RuntimeException(error); }
                        });
                        String data = JSON.toJson(position) + "\n";
                        Path runtime = sessionDir.getParent().getParent();
                        Files.writeString(runtime.resolve("player-position.json"), data);
                        Files.writeString(runtime.resolve("player-positions.jsonl"), data,
                            java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
                        response = data.getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/hover" -> {
                        Map<?, ?> point = JSON.fromJson(new String(exchange.getRequestBody().readNBytes(512), java.nio.charset.StandardCharsets.UTF_8), Map.class);
                        int x = ((Number) point.get("x")).intValue(), y = ((Number) point.get("y")).intValue();
                        SwingUtilities.invokeAndWait(() -> {
                            for (Frame frame : Frame.getFrames()) {
                                if (drawable(frame) instanceof Component canvas && canvas.isShowing()) {
                                    if (x < 0 || y < 0 || x >= canvas.getWidth() || y >= canvas.getHeight())
                                        throw new IllegalArgumentException("Hover outside canvas");
                                    canvas.dispatchEvent(new MouseEvent(canvas, MouseEvent.MOUSE_MOVED, System.currentTimeMillis(), 0, x, y, 0, false, MouseEvent.NOBUTTON));
                                    return;
                                }
                            }
                            throw new IllegalStateException("No visible canvas");
                        });
                        response = "ok".getBytes();
                    }
                    case "/pick-cell" -> {
                        Map<?, ?> point = JSON.fromJson(new String(exchange.getRequestBody().readNBytes(512), java.nio.charset.StandardCharsets.UTF_8), Map.class);
                        Map<String,Object> picks = new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> {
                            try {
                                Object manager = call(Class.forName("aGZ"),"cfK"), scene = call(manager,"bmC");
                                float x=((Number)point.get("x")).floatValue(), y=((Number)point.get("y")).floatValue();
                                float height=((Number)call(scene,"bRV")).floatValue();
                                for (String pickMode : new String[]{"bWP","bWQ"}) {
                                for (float scale : new float[]{1,2}) {
                                    for (boolean flip : new boolean[]{false,true}) {
                                        float px=x*scale,py=flip?height-y*scale:y*scale;
                                        java.util.List<?> tiles=(java.util.List<?>)Class.forName("Zi").getMethod("a",float.class,float.class,float.class,Class.forName("Zq")).invoke(scene,px,py,0f,field(Class.forName("Zq"),pickMode));
                                        java.util.List<Map<String,Object>> values=new ArrayList<>();
                                        for(Object tile:tiles) {
                                            Map<String,Object> value=new LinkedHashMap<>();
                                            value.put("class",tile.getClass().getName());
                                            for(String key:new String[]{"bcz","bcA","bcB","bro"})value.put(key,call(tile,key));
                                            try {value.put("bqo",call(tile,"bqo"));} catch(NoSuchMethodException ignored) {}
                                            values.add(value);
                                        }
                                        picks.put(pickMode+"_scale"+scale+"_flip"+flip,values);
                                    }
                                }
                                }
                                picks.put("scene_height",height);
                            } catch(Exception error) {picks.put("error",error.toString());}
                        });
                        response=(JSON.toJson(picks)+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/equipment-diagnostic" -> {
                        Map<String,Object> diagnostic = new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> diagnostic.putAll(equipmentDiagnostic()));
                        response = (JSON.toJson(diagnostic) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/spell-availability" -> {
                        Map<?,?> input=JSON.fromJson(new String(exchange.getRequestBody().readNBytes(512),java.nio.charset.StandardCharsets.UTF_8),Map.class);
                        long actorId=Long.parseLong(String.valueOf(input.get("actor_id")));
                        long spellUid=Long.parseLong(String.valueOf(input.get("spell_uid")));
                        Map<String,Object> diagnostic=new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> {
                            try {
                                Object fight=call(call(Class.forName("dba"),"fcm"),"cXY");
                                Object actor=call(fight,"rj",actorId);
                                Object book=call(actor,"js",spellUid);
                                diagnostic.put("actor_id",actorId);
                                diagnostic.put("spell_uid",spellUid);
                                diagnostic.put("count",call(actor,"dTB"));
                                Object original=call(fight,"a",actor,book,null,true);
                                diagnostic.put("null_target",String.valueOf(original));
                                diagnostic.put("policy",String.valueOf(NativeSpellAvailability.withNativeContext(original,fight,actor,book)));
                                List<Map<String,Object>> candidates=new ArrayList<>();
                                for(Object target:(java.util.Collection<?>)call(fight,"dLy")) {
                                    Map<String,Object> row=new LinkedHashMap<>();
                                    row.put("id",call(target,"Sn"));
                                    row.put("breed",call(target,"aXA"));
                                    Object owner=call(target,"dpr");
                                    row.put("owner",owner==null?null:call(owner,"Sn"));
                                    row.put("query",String.valueOf(call(fight,"a",actor,book,call(target,"baM"),true)));
                                    candidates.add(row);
                                }
                                diagnostic.put("candidates",candidates);
                            }catch(Throwable error){diagnostic.put("error",error.toString());}
                        });
                        response=(JSON.toJson(diagnostic)+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/combat-actor" -> {
                        Map<?,?> input=JSON.fromJson(new String(exchange.getRequestBody().readNBytes(512),java.nio.charset.StandardCharsets.UTF_8),Map.class);
                        long identity=Long.parseLong(String.valueOf(input.get("actor_id")));
                        Map<String,Object> diagnostic=new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> {
                            diagnostic.put("time",Instant.now().toString());
                            try {
                                Object fight=call(call(Class.forName("dba"),"fcm"),"cXY");
                                Object fighter=call(fight,"rj",identity);
                                diagnostic.put("fight",String.valueOf(fight));
                                if(fighter==null)throw new IllegalStateException("Combat actor absent");
                                diagnostic.put("id",call(fighter,"Sn"));
                                Map<String,Object> summonCount=new LinkedHashMap<>();
                                summonCount.put("count",call(fighter,"dTB"));
                                List<Map<String,Object>> countPopulation=new ArrayList<>();
                                for(Object candidate:(java.util.Collection<?>)call(fight,"dLy")) {
                                    Map<String,Object> row=new LinkedHashMap<>();
                                    row.put("id",call(candidate,"Sn"));
                                    row.put("breed",call(candidate,"aXA"));
                                    row.put("is_summon",call(candidate,"dTE"));
                                    row.put("is_dead",call(candidate,"dsA"));
                                    Object controller=call(candidate,"dpr");
                                    row.put("controller_id",controller==null?null:call(controller,"Sn"));
                                    row.put("controller_is_selected_actor",controller==fighter);
                                    row.put("excluded_property_103",call(candidate,"i",call(Class.forName("ffe"),"Ua",103)));
                                    countPopulation.add(row);
                                }
                                summonCount.put("population",countPopulation);
                                diagnostic.put("native_summon_count",summonCount);
                                diagnostic.put("position",List.of(call(fighter,"getWorldX"),call(fighter,"getWorldY"),call(fighter,"getAltitude")));
                                Map<String,Object> stats=new LinkedHashMap<>();
                                for(Object definition:(Object[])call(Class.forName("ffw"),"values")){
                                    stats.put(String.valueOf(call(definition,"aKg")),call(fighter,"c",definition));
                                }
                                diagnostic.put("stats",stats);
                                // Read the actual retained manager, not delivery packets.
                                // eZk carriers can be observed without being registered.
                                try {
                                    Object manager=call(fighter,"drJ");
                                    java.util.Iterator<?> retained=(java.util.Iterator<?>)call(manager,"iterator");
                                    List<Map<String,Object>> effects=new ArrayList<>();
                                    while(retained.hasNext()) {
                                        Object effect=retained.next();
                                        Map<String,Object> entry=new LinkedHashMap<>();
                                        entry.put("runner",effect.getClass().getName());
                                        entry.put("uid",call(effect,"LV"));
                                        entry.put("effect_class",call(effect,"d"));
                                        entry.put("value",call(effect,"getValue"));
                                        if(Class.forName("eZk").isInstance(effect)) {
                                            Object definition=call(effect,"fQW");
                                            entry.put("state_id",call(definition,"guI"));
                                            entry.put("state_level",call(definition,"cmZ"));
                                        }
                                        effects.add(entry);
                                    }
                                    diagnostic.put("running_effects",effects);
                                }catch(Throwable error){diagnostic.put("running_effects_error",error.toString());}
                                // Combat eGj does not expose the visual actor getDirection.
                                // Read only the proven characteristic getter here.
                                diagnostic.put("maximum_hp",call(call(fighter,"e",field(Class.forName("ffw"),"sgC")),"aYU"));
                            }catch(Throwable error){diagnostic.put("error",error.toString());}
                        });
                        response=(JSON.toJson(diagnostic)+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/movement-diagnostic" -> {
                        Map<String,Object> diagnostic=new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> diagnostic.putAll(movementDiagnostic()));
                        response=(JSON.toJson(diagnostic)+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/combat-diagnostic" -> {
                        Map<String,Object> diagnostic = new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> diagnostic.putAll(combatDiagnostic()));
                        response = (JSON.toJson(diagnostic) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/interactive-registry" -> {
                        Map<?,?> input=JSON.fromJson(new String(exchange.getRequestBody().readNBytes(8192),java.nio.charset.StandardCharsets.UTF_8),Map.class);
                        Object rawIds=input==null?null:input.get("object_ids");
                        if(rawIds==null&&input!=null)rawIds=input.get("generalObjectIds");
                        List<Long> ids=new ArrayList<>();
                        if(rawIds==null)ids.addAll(List.of(26865L,26842L));
                        else {
                            if(!(rawIds instanceof List<?> values)||values.isEmpty()||values.size()>64)
                                throw new IllegalArgumentException("object_ids must contain 1..64 IDs");
                            for(Object value:values) {
                                if(value instanceof Number n)ids.add(n.longValue());
                                else if(value instanceof String s)ids.add(Long.parseLong(s));
                                else throw new IllegalArgumentException("object IDs must be integers or decimal strings");
                            }
                        }
                        Map<String,Object> diagnostic=new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> diagnostic.putAll(interactiveRegistryDiagnostic(ids)));
                        response=(JSON.toJson(diagnostic)+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/project-cell" -> {
                        Map<?, ?> cell = JSON.fromJson(new String(exchange.getRequestBody().readNBytes(512), java.nio.charset.StandardCharsets.UTF_8), Map.class);
                        Map<String, Object> point = new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> {
                            try {
                                Object manager = Class.forName("aGZ").getMethod("cfK").invoke(null);
                                Object scene = manager.getClass().getMethod("bmC").invoke(manager);
                                Object projected = Class.forName("afh").getMethod("c", Class.forName("aeU"), float.class, float.class, float.class).invoke(null, scene,
                                    ((Number) cell.get("x")).floatValue(), ((Number) cell.get("y")).floatValue(), ((Number) cell.get("z")).floatValue());
                                double sx = projected.getClass().getField("aRt").getFloat(projected);
                                double sy = projected.getClass().getField("aRu").getFloat(projected);
                                double width = ((Number) scene.getClass().getMethod("bRU").invoke(scene)).doubleValue();
                                double height = ((Number) scene.getClass().getMethod("bRV").invoke(scene)).doubleValue();
                                for (Frame frame : Frame.getFrames()) {
                                    if (drawable(frame) instanceof Component canvas && canvas.isShowing()) {
                                        point.put("x", Math.round(sx * canvas.getWidth() / width));
                                        point.put("y", Math.round((height - sy) * canvas.getHeight() / height));
                                        point.put("sceneWidth", width);
                                        point.put("sceneHeight", height);
                                        return;
                                    }
                                }
                                throw new IllegalStateException("No visible canvas");
                            } catch (Exception error) { throw new RuntimeException(error); }
                        });
                        response = (JSON.toJson(point) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/drag" -> {
                        Map<?,?> p=JSON.fromJson(new String(exchange.getRequestBody().readNBytes(512),java.nio.charset.StandardCharsets.UTF_8),Map.class);
                        dragCanvas(((Number)p.get("x")).intValue(),((Number)p.get("y")).intValue(),((Number)p.get("end_x")).intValue(),((Number)p.get("end_y")).intValue());
                        response="ok".getBytes();
                    }
                    case "/click" -> {
                        Map<?, ?> point = JSON.fromJson(new String(exchange.getRequestBody().readNBytes(512), java.nio.charset.StandardCharsets.UTF_8), Map.class);
                        int x = ((Number) point.get("x")).intValue(), y = ((Number) point.get("y")).intValue();
                        append(new LinkedHashMap<>(Map.of("event", "action", "label", "canvas_left_click", "x", x, "y", y)));
                        int button = point.get("button") instanceof Number value ? value.intValue() : MouseEvent.BUTTON1;
                        int count = point.get("count") instanceof Number value ? value.intValue() : 1;
                        clickCanvas(x, y, button, count);
                        response = "ok".getBytes();
                    }
                    case "/screen" -> {
                        response = screenshot();
                        exchange.getResponseHeaders().set("Content-Type", "image/png");
                    }
                    case "/canvas-info" -> {
                        Map<String, Object> state = new LinkedHashMap<>();
                        SwingUtilities.invokeAndWait(() -> {
                            for (Frame frame : Frame.getFrames()) {
                                GLAutoDrawable gl = drawable(frame);
                                if (gl instanceof Component canvas) {
                                    state.put("canvas_width", canvas.getWidth());
                                    state.put("canvas_height", canvas.getHeight());
                                    state.put("surface_width", gl.getSurfaceWidth());
                                    state.put("surface_height", gl.getSurfaceHeight());
                                    state.put("frame_x", frame.getX());
                                    state.put("frame_y", frame.getY());
                                    return;
                                }
                            }
                            throw new IllegalStateException("No visible canvas");
                        });
                        response = (JSON.toJson(state) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                    case "/mark" -> {
                        String label = new String(exchange.getRequestBody().readNBytes(2048), java.nio.charset.StandardCharsets.UTF_8);
                        append(new LinkedHashMap<>(Map.of("event", "action", "label", label)));
                        response = "ok".getBytes();
                    }
                    default -> {
                        List<Map<String, Object>> nodes = new ArrayList<>();
                        SwingUtilities.invokeAndWait(() -> { for (Frame frame : Frame.getFrames()) collect(frame, nodes); });
                        response = JSON.toJson(nodes).getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    }
                }
                exchange.sendResponseHeaders(200, response.length);
                exchange.getResponseBody().write(response);
            } catch (Exception error) {
                byte[] message = error.getClass().getSimpleName().getBytes();
                exchange.sendResponseHeaders(500, message.length);
                exchange.getResponseBody().write(message);
            } finally { exchange.close(); }
        });
        server.start();
    }
}
