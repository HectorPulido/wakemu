import java.lang.reflect.*;
import java.nio.file.*;
/** Actual eYB.d -> SQ SET, distinct from eYw SP. */
public class ProbeNativeTriggerValueGroup {
 static Field field(Object o,String n)throws Exception{for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);return f;}catch(NoSuchFieldException e){}throw new NoSuchFieldException(n);}
 public static void main(String[]args)throws Exception{
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  eYB runner=new eYB();runner.b(bcA.dcX().AH(409764));runner.C(null);
  for(float[]p:new float[][]{{100,0},{50,1},{-50,-1},{1e20f,0}}){
   field(runner,"rGe").setFloat(runner,p[0]);field(runner,"rGs").setFloat(runner,p[1]);
   for(int v:new int[]{5,-5,Integer.MAX_VALUE}){
    eXE source=new eXE();field(source,"aSg").setInt(source,v);
    eVt context=runner.d(source,false);int expected=(int)(v*p[0]/100f+p[1]);
    if(context.Ol()!=expected||context.fLS()!=eVu.ryv||context.Oh()!=-1)throw new AssertionError(context.Ol());
    context.bal();
   }
  }
  eVt absent=runner.d(null,false);if(absent.fLR()||absent.Oh()!=-1)throw new AssertionError();absent.bal();
  field(runner,"rGe").setFloat(runner,50);field(runner,"rGs").setFloat(runner,1);
  eXE source=new eXE();field(source,"aSg").setInt(source,5);eVt codec=runner.d(source,false);
  if(args.length>0)Files.write(Path.of(args[0]),codec.fLV().toByteArray());codec.bal();
  System.out.println("eYB1103 original: 12 float/SET/SP cases and absent source: 13 PASS");
 }
}
