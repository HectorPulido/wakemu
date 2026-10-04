import java.lang.reflect.*;
/** Offline eXE400 original subscription and Qe.k clone identity/state. */
public class ProbeNativeNullListener {
 static long next=901;
 static class NullListener extends eXE {
  static iN before; static NullListener copy;
  public NullListener fPk(){return new NullListener();}
  public boolean i(Qe source){return true;}
  public boolean L(byte channel){return false;}
  protected boolean bbZ(){return false;}
  protected void c(Qe source,boolean event){before=bca();copy=this;}
  void initialize(){bfr=ProbeNativeEffectUIDs.actor(7);bfs=ProbeNativeEffectUIDs.actor(-7);
   bfp=(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(p,m,a)->switch(m.getName()){
    case "fLb"->false;case "fKJ"->0;case "aZE"->359836;case "aZD"->(byte)2;case "en","eo"->Tt.pz(0);
    case "aZO"->new java.util.BitSet();case "aZV"->Qd.bfe;case "aZW"->Qb.beO;
    case "toString"->"NullListenerDefinition";default->throw new UnsupportedOperationException(m.getName());});
  }
 }
 public static void main(String[]args)throws Exception{
  org.apache.log4j.BasicConfigurator.configure();Qe.a(()->next++);
  NullListener prototype=new NullListener();prototype.initialize();
  NullListener listener=(NullListener)prototype.bbm();
  if(listener.QH().Pk()!=-1||listener.QH().MB()||listener.LV()!=901||listener.bca().Qq()!=901)
   throw new AssertionError("Original null listener constructor state");
  iN originalPayload=listener.bca();
  listener.k(prototype);
  eXE clone=new eXE();clone.lV(400);clone.ds(NullListener.before.toByteArray());
  if(clone.LV()!=902||NullListener.before.Qq()!=901||clone.QH().Pk()!=-1||clone.QH().MB())
   throw new AssertionError("Cloned listener pre-application decoded identity/state");
  clone.a(null,true);
  if(!clone.QH().MB())throw new AssertionError("Clone executed state");
  eXE original=new eXE();original.lV(400);original.ds(originalPayload.toByteArray());
  if(original.LV()!=901||original.QH().MB())throw new AssertionError("Original remains unexecuted");
  System.out.println("eXE400 original UID901/base901 status-1 executed=false; clone UID902/base901 status-1 executed=true, native decode PASS");
  if(args.length==2){
   apw.bGL().dd("jar:file:"+java.nio.file.Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
   bPS.elL();
   eXE received=new eXE();received.lV(400);received.ds(java.nio.file.Files.readAllBytes(java.nio.file.Path.of(args[0])));
   eXE receivedClone=new eXE();receivedClone.lV(400);receivedClone.ds(java.nio.file.Files.readAllBytes(java.nio.file.Path.of(args[1])));
   if(received.LV()!=901||received.bca().Qq()!=901||received.QH().MB()
       ||receivedClone.LV()!=902||receivedClone.bca().Qq()!=901||!receivedClone.QH().MB())
    throw new AssertionError("Python null listener payload native decode");
   System.out.println("Python original/clone eXE400 -> native decoder PASS");
  }
  Qe.a((Qh)null);
 }
}
