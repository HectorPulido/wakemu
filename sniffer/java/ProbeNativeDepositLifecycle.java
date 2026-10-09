import java.nio.file.Path;
import java.lang.reflect.Proxy;
import java.util.*;

/** Installed native faU constructors, Qq identity and recipient contracts. */
public class ProbeNativeDepositLifecycle {
 public static void main(String[] args){
  apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
  int[] count={0};
  apw.bGL().a(new aKa(),new apB<aKa>(){public void load(aKa raw){
   faV prototype=bcN.hFx.a(raw);if(!(prototype instanceof faU))return;
   faU area=(faU)prototype.b(new fbm(9000+raw.d(),2,3,(short)9,null,7,null,(short)1,aAS.wL(0)));
   area.bcT();
   if(area.aeV()!=12||area.aZY()!=3||area.fTu()!=(int)raw.bdh()[0])
    throw new AssertionError("native deposit constructor");
   if(!area.baF()||area.baG()||area.baK()||area.bcO()||area.bcP())
    throw new AssertionError("native deposit PV lifecycle");
   if((area.bax()!=null)!=Arrays.stream(raw.ckE()).anyMatch(x->x==12))
    throw new AssertionError("native deposit nullable Qf");
   if(!area.e((amP)null)||area.c((amP)null)!=null||area.d((amP)null)!=null)
    throw new AssertionError("native deposit null recipient");
   amP target=(amP)Proxy.newProxyInstance(amP.class.getClassLoader(),new Class[]{amP.class},
    (p,m,a)->switch(m.getName()){
     case "bcz"->5;case "bcA"->6;case "bcB"->(short)-2;
     case "equals"->p==a[0];case "toString"->"ExplicitTarget";
     default->throw new UnsupportedOperationException(m.getName());
    });
   if(area.c(target)[0]!=ama.L(5,6,(short)-2)||!area.d(target).equals(List.of(target)))
    throw new AssertionError("native deposit actual recipient");
   if(!area.d(new aBn(2,3,(short)-99))||area.bcK()!=0||area.bcL()!=0)
    throw new AssertionError("native deposit cached geometry/radius/height");
   count[0]++;
  }});
  if(count[0]==0)throw new AssertionError("missing installed faU prototypes");
  System.out.println("PASS installed faU prototypes="+count[0]+" grade/identity/Qf/guards/recipient/geometry");
 }
}
