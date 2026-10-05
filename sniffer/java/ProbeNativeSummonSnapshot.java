import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
/** Actual bje lazy characteristics and eHD transform, no aQc graphical path. */
public class ProbeNativeSummonSnapshot {
 public static void main(String[]args)throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  Method convert=bbo.class.getDeclaredMethod("a",aMb.class,short.class);convert.setAccessible(true);
  Map<Integer,blj> wanted=new HashMap<>();
  apw.bGL().a(new aMb(),new apB<aMb>(){public void load(aMb r){
   if(r.d()==3791||r.d()==5525)try{wanted.put(r.d(),(blj)convert.invoke(null,r,(short)r.d()));}catch(Exception e){throw new RuntimeException(e);}
  }});
  bje caster=bje.dsi();caster.dA(7);caster.c(wanted.get(5525));caster.bz((short)20);caster.dpQ();
  bje sphere=bje.dsi();sphere.dA(901);sphere.c(wanted.get(3791));sphere.bz((short)20);sphere.dpQ();
  Method prepare=bje.class.getDeclaredMethod("drd");prepare.setAccessible(true);prepare.invoke(sphere);
  eHD descriptor=new eHD((short)3791,"",-1,(short)20);descriptor.lZ(901);
  descriptor.M((byte)0);descriptor.a(aAS.dyw);descriptor.au((byte)0);descriptor.a(sphere,caster);
  for(ffw stat:new ffw[]{ffw.sgC,ffw.sgD,ffw.sgE,ffw.sgF,ffw.shc})
   System.out.println((stat.aKg()&255)+":"+sphere.e(stat).aYS()+"/"+sphere.e(stat).aYU());
  if(sphere.c(ffw.sgC)!=1||sphere.c(ffw.sgD)!=0||sphere.c(ffw.sgE)!=0||sphere.c(ffw.sgF)!=0)
   throw new AssertionError("Native sphere resources");
  if(sphere.fqd()!=descriptor)throw new AssertionError("descriptor attachment");
  System.out.println("PASS actual bje/eHD sphere3791 level20 snapshot; graphical aQc intentionally excluded");
 }
}
