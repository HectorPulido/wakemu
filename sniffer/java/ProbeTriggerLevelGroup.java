import java.nio.file.*;import java.lang.reflect.*;
public class ProbeTriggerLevelGroup {
 static Field field(Object o,String n)throws Exception{for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);return f;}catch(NoSuchFieldException e){}throw new NoSuchFieldException(n);}
 public static void main(String[]a)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 eVn d=bcA.dcX().AH(308066);System.out.println("actual generic="+d.awM()+" parameter count="+d.fKJ());
 eYw runner=new eYw();runner.b(d);runner.C(null);System.out.println("actual ratio="+field(runner,"rGe").getFloat(runner));
 field(runner,"rGe").setFloat(runner,.5f);
 for(int value:new int[]{5,-5}){eXE source=new eXE();field(source,"aSg").setInt(source,value);int got=field(runner.d(source,false),"ryo").getInt(runner.d(source,false));if(got!=(value>0?2:-2))throw new AssertionError(got);System.out.println("actual trigger="+value+" ratio=.5 override="+got);}
 int absent=field(runner.d(null,false),"ryo").getInt(runner.d(null,false));if(absent!=-1)throw new AssertionError(absent);System.out.println("actual absent source override=-1");
 }
}
