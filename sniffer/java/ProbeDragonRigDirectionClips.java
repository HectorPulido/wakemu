import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.jar.*;
import com.ankamagames.framework.graphics.engine.Anm2.Anm;

/** Executes native YJ direction naming, ANM parsing and aqj clip lookup for Dragon rigs 26/27. */
public class ProbeDragonRigDirectionClips {
  static Object unsafeAllocate(Class<?> type) throws Exception {
    Field f=Class.forName("sun.misc.Unsafe").getDeclaredField("theUnsafe"); f.setAccessible(true);
    return ((sun.misc.Unsafe)f.get(null)).allocateInstance(type);
  }
  static String[] names(Fl fl) { return Arrays.stream(fl.aKy()).map(Fk::getName).toArray(String[]::new); }
  public static void main(String[] args) throws Exception {
    try(JarFile jar=new JarFile("client/contents/animations/players/players.jar")) {
      for(String asset:new String[]{"26.anm","27.anm"}) {
        byte[] bytes; try(InputStream in=jar.getInputStream(jar.getJarEntry(asset))){bytes=in.readAllBytes();}
        Constructor<Anm> ctor=Anm.class.getDeclaredConstructor(); ctor.setAccessible(true); Anm anim=ctor.newInstance();
        Field path=Anm.class.getDeclaredField("axV"); path.setAccessible(true); path.set(anim,asset.substring(0,asset.length()-4));
        Method parse=Anm.class.getDeclaredMethod("dB",byte[].class); parse.setAccessible(true); parse.invoke(anim,(Object)bytes);
        Fl fl=anim.aJs(); if(fl==null) throw new AssertionError("native ANM parser yielded no Fl for "+asset);
        aqj selector=(aqj)unsafeAllocate(aqj.class); Field base=aqj.class.getDeclaredField("cQc"); base.setAccessible(true); base.set(selector,anim);
        Method normalize=aqj.class.getDeclaredMethod("gd",String.class); normalize.setAccessible(true);
        System.out.println(asset+" flags="+fl.aJa()+" compact="+fl.aKG());
        for(int direction=0;direction<8;direction++) {
          final int dir=direction;
          YJ actor=(YJ)unsafeAllocate(YJ.class);
          aAS nativeDirection=Arrays.stream(aAS.values()).filter(value->value.dyI==dir).findFirst().orElseThrow();
          Field actorDirection=YJ.class.getDeclaredField("bkU"); actorDirection.setAccessible(true); actorDirection.set(actor,nativeDirection);
          String raw=actor.en("AnimStatique");
          String selected=(String)normalize.invoke(selector,raw);
          boolean found=fl.by(selected)!=null;
          boolean expected=(direction&1)==1;
          if(found!=expected) throw new AssertionError(asset+" direction="+direction+" requested="+raw+" selected="+selected+" clip="+found);
          System.out.println("direction="+direction+" requested="+raw+" selected="+selected+" clip="+found);
        }
      }
    }
  }
}
