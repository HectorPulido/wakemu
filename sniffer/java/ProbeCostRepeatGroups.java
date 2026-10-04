import java.nio.file.*;import java.lang.reflect.*;
public class ProbeCostRepeatGroups {
 static Field field(Object o,String n)throws Exception{for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);return f;}catch(NoSuchFieldException e){}throw new NoSuchFieldException(n);}
 static void costs(eWf c,byte ap,byte mp,byte wp)throws Exception{Method m=eWf.class.getDeclaredMethod("f",byte.class,byte.class,byte.class,byte.class);m.setAccessible(true);m.invoke(c,ap,mp,wp,(byte)0);}
 static int override(eVt c)throws Exception{return field(c,"ryo").getInt(c);}
 public static void main(String[]a)throws Exception{
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
 eYt r=new eYt();r.b(bcA.dcX().AH(348490));r.C(null);
 eWf cost=new eWf();costs(cost,(byte)3,(byte)4,(byte)2);
 int actual=override(r.d(cost,false));if(actual!=4)throw new AssertionError(actual);
 if(override(r.d(null,false))!=-1||override(r.d(new eXE(),false))!=-1)throw new AssertionError("missing/noncost");
 System.out.println("912 actual348490 paidMP4→level4; null/non-eWf→SP-1");
 field(r,"rFX").setFloat(r,.5f);field(r,"rFY").setFloat(r,0f);field(r,"rFZ").setFloat(r,0f);
 costs(cost,(byte)-3,(byte)0,(byte)0);if(override(r.d(cost,false))!=-1)throw new AssertionError("negative round");
 eYv spell=new eYv();spell.b(bcA.dcX().AH(308144));spell.C(null);
 eXE nonspell=new eXE();nonspell.b(bcA.dcX().AH(348491));if(override(spell.d(null,false))!=0||override(spell.d(nonspell,false))!=0)throw new AssertionError("910 null/nonspell");
 System.out.println("910 actual308144 null/nospell→SP0; spell-context-cost path requires real fyG/PN");
 eXL repeat=new eXL();repeat.b(bcA.dcX().AH(379582));repeat.C(null);
 if(field(repeat,"rEE").getInt(repeat)!=6||!field(repeat,"rEF").getBoolean(repeat))throw new AssertionError("949");
 System.out.println("949 actual379582 repeat6 stopfailureTrue");
 }
}
