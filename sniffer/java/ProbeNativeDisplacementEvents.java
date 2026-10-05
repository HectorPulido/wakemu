/** Original runner masks, without invented external turn/movement events. */
public class ProbeNativeDisplacementEvents {
 static java.util.List<String> phases=new java.util.ArrayList<>();static long next=900;
 static class Pull extends eXJ {
  public Pull fPr(){return new Pull();}
  public boolean i(Qe source){return true;}
  public void C(Qe source){super.C(source);if(getValue()!=0)throw new AssertionError("Calculation populated aSg");}
  protected void c(Qe source,boolean event){aSg=2;} // Isolate lifecycle from terrain renderer.
  public boolean L(byte channel){phases.add(channel+":"+getValue()+":"+bbw());return false;}
  protected boolean bbZ(){return false;}
  void initialize(eVn definition){bfr=ProbeNativeEffectUIDs.actor(7);bfs=ProbeNativeEffectUIDs.actor(-7);bfp=definition;bba();}
 }
 public static void main(String[]args)throws Exception {
  for(int kind:new int[]{300,301,302,340,331,422}) {
   eZR runner=eVi.fLJ().pS(kind);runner.bbx();
   System.out.println(kind+" "+runner.getClass().getName()+" "+runner.bbw());
   if(runner.bbw().get(1002)||runner.bbw().get(204))throw new AssertionError("Collision/external event was incorrectly a base mask");
  }
  apw.bGL().dd("jar:file:"+java.nio.file.Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw raw){}});
  Qe.a(()->next++);
  Pull prototype=new Pull();prototype.initialize(bcA.dcX().AH(326690));
  Pull fresh=(Pull)prototype.bbm();fresh.a(new eZV(ProbeNativeEffectUIDs.actor(-7)));fresh.k(prototype);
  System.out.println("Original Qe.k/eZR lifecycle: "+phases);
  if(!phases.equals(java.util.List.of("1:0:{0, 185, 188}","2:0:{0, 185, 188}","3:2:{0, 185, 188}","4:2:{0, 185, 188}")))throw new AssertionError(phases);
  Qe.a((Qh)null);
 }
}
