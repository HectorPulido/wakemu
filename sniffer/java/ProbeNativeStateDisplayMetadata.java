import java.nio.file.Path;
/** Installed native state definitions; no actor mutation or GUI dependency. */
public final class ProbeNativeStateDisplayMetadata {
 public static void main(String[] args) throws Exception {
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  fyZ.guX().a(new bbV());
  for(int reference:new int[]{3442,8913}) {
   bQh base=(bQh)fyZ.guX().aax(reference);
   if(base==null)throw new AssertionError("missing definition");
   for(short level:new short[]{1,10,30,50}) {
    bQh state=(bQh)base.cu(level);
    java.lang.reflect.Field iconField=bQh.class.getDeclaredField("bcw");iconField.setAccessible(true);
    String icon=(String)iconField.get(state);
    try(java.util.jar.JarFile jar=new java.util.jar.JarFile("client/contents/gui_jar/gui.jar")){
     if(jar.getEntry("icons/states/"+icon+".tga")==null)throw new AssertionError("missing native icon "+icon);
    }
    System.out.println("state="+reference+" level="+state.cmZ()+" display(elv)="+state.elv()+" cxv="+state.cxv()+" category="+state.elk()+" icon="+icon+" definitionType="+state.aZY());
    if(!state.elv())throw new AssertionError("expected native display eligibility");
    for(eVn effect:state.guJ()) {
     System.out.println(" child="+effect.aZE()+" effectClass="+effect.awM()+" cys="+effect.cys()+" fKP="+effect.fKP()+" script="+effect.cbx());
     Qe runner=effect.awM()==400?new eXE():new eYg();runner.lV(effect.awM());
     java.lang.reflect.Field pk=Qe.class.getDeclaredField("bfp");pk.setAccessible(true);pk.set(runner,effect);
     java.lang.reflect.Field pl=Qe.class.getDeclaredField("bfq");pl.setAccessible(true);
     if(new bPG().c(runner,-1)!=null)throw new AssertionError("null container unexpectedly displayed");
     pl.set(runner,state);
     bPE display=new bPG().c(runner,-1);
     if((display!=null)!=effect.cys())throw new AssertionError("native cys display gate mismatch");
     if(display!=null && (display.elp()!=1 || display.elm()!=state.cmZ()))throw new AssertionError("native state display data mismatch");
    }
   }
  }
  System.out.println("PASS: both states native display-eligible at all tested levels");
 }
}
