import com.google.protobuf.Message;import java.nio.file.*;import java.lang.reflect.*;
public class ProbeParameterMaximum {
 static Field field(Object o,String n)throws Exception{for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);return f;}catch(NoSuchFieldException e){}throw new NoSuchFieldException(n);}
 static void mutate(eWU r,fff p,String method)throws Exception{Method m=r.getClass().getDeclaredMethod(method,PA.class);m.setAccessible(true);m.invoke(r,p);}
 public static void main(String[]a)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 for(int ref:new int[]{345698,345699}){eVn def=bcA.dcX().AH(ref);eWU r=def.awM()==1202?new eWT():new eWS();r.b(def);r.C(null);
 System.out.println("native ref="+ref+" family="+def.awM()+" stat="+r.fNI().aKg()+" amount="+r.getValue());
 fff p=new fff(ffw.fK((byte)117),0,30);p.or(30);p.on(25);mutate(r,p,"d");if(p.aYV()!=(def.awM()==1202?20:40))throw new AssertionError("raw");System.out.println("after current="+p.aYT()+" raw="+p.aYV()+" max="+p.aYU());
 mutate(r,p,"e");if(p.aYV()!=(def.awM()==1202?30:20))throw new AssertionError("remove");System.out.println("remove current="+p.aYT()+" raw="+p.aYV()+" max="+p.aYU());}
 System.out.println("additional="+java.util.HexFormat.of().formatHex(((Message.Builder)ij.MR().em(117)).build().toByteArray()));
 eWT r=new eWT();field(r,"aSg").setInt(r,50);fff p=new fff(ffw.fK((byte)117),0,30);p.or(30);mutate(r,p,"d");if(r.getValue()!=0||p.aYV()!=0)throw new AssertionError("clamp");System.out.println("clamp amount="+r.getValue()+" raw="+p.aYV());mutate(r,p,"e");System.out.println("clamp remove raw="+p.aYV());
 }
}
