import java.nio.file.*;
public class ProbeNativeStateRemovalGate {
 static class Remove extends aVz {Remove(eZk r)throws Exception{super(1,0,7,310,r,r.LV(),-200,new byte[0]);ProbeNativeStateManager.set(this,aVz.class,"hty",r);}void execute(){super.cbj();}}
 public static void main(String[] args)throws Exception {
 apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");fyZ.guX().a(new bbV());
 for(String file:args){cvX msg=new cvX();msg.dp(Files.readAllBytes(Path.of(file)));byte[] body=msg.eIJ();var c=new ProbeNativeStateManager.Collection();var t=new ProbeNativeStateManager.Collection();PV caster=ProbeNativeStateManager.actor(20,c),target=ProbeNativeStateManager.actor(-200,t);eZk r=ProbeNativeStateManager.decoded(body,caster,target);var a=new ProbeNativeStateManager.Complete(r,caster,target);a.cYb();a.fe(target.Sn());a.iD(caster.Sn());a.cYc();a.cbj();if(r.fMV())throw new AssertionError("old unexpected removable");new Remove(r).execute();if(t.fSs().size()!=1)throw new AssertionError("old unexpectedly removed");
 iN old=iN.bf(body);iB timing=old.QH();iB replacement=iB.Pr().c(timing).G(true).Py();r.f(replacement);if(!r.fMV())throw new AssertionError("removal gate false");new Remove(r).execute();if(!t.fSs().isEmpty())throw new AssertionError("state not removed");System.out.println("PASS state"+r.fQW().guI()+" removal timing field1 changes fMV false to true, Qf.q clears carrier");
 }
 }
}