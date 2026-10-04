import java.nio.file.*;import java.util.*;
/** Actual Qe.k/eZR lifecycle with a real aZO1002 eYg definition; no guessed phase6. */
public class ProbeNativeEvent1002Lifecycle {
 static List<Integer> phases=new ArrayList<>();static long next=900;
 static class Source extends eYg {
  public Source fPD(){return new Source();}
  public boolean i(Qe source){return true;}
  public void C(Qe source){} // Isolate routing from children/condition execution.
  protected void c(Qe source,boolean event){}
  public boolean L(byte channel){
   if(!bbw().get(1002))throw new AssertionError("Real definition lost aZO1002");
   phases.add((int)channel);return false;
  }
  protected boolean bbZ(){return false;}
  void initialize(eVn definition){bfr=ProbeNativeEffectUIDs.actor(7);bfs=ProbeNativeEffectUIDs.actor(-7);bfp=definition;bba();}
 }
 public static void main(String[]args)throws Exception{
  org.apache.log4j.BasicConfigurator.configure();
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw definition){}});
  Qe.a(()->next++);
  for(int reference:new int[]{196837,289926,299976,338934}){
   eVn definition=bcA.dcX().AH(reference);
   if(definition.awM()!=330||!definition.aZO().get(1002)||!definition.aZL().get(1015)||!definition.aZL().get(1025))
    throw new AssertionError("Real native event1002 source definition");
   Source prototype=new Source();prototype.initialize(definition);
   Source fresh=(Source)prototype.bbm();fresh.a(new eZV(ProbeNativeEffectUIDs.actor(-7)));phases.clear();fresh.k(prototype);
   if(!phases.equals(List.of(1,2,3,4)))throw new AssertionError("Unexpected native source lifecycle "+phases);
   System.out.println(reference+" native aZO1002 accepted clone phases="+phases+"; no phase6");
  }
  Qe.a((Qh)null);
 }
}
