import java.nio.*;
import java.nio.file.*;
/** Native kX56/le, vj/vo/vR, foX mapping and eWW -1 copy semantics. Offline. */
public class ProbeNativeEquipmentElements {
 public static void main(String[] args) throws Exception {
  kX item=kX.bG(Files.readAllBytes(Path.of(args[0])));
  if(!item.isInitialized()||!item.aec())throw new AssertionError("missing elements");
  le elements=item.aed();int damage=elements.afm(),resist=elements.afo();
  foX selected=new foX();foX.a(selected,(byte)damage,eVi.rpX.d());foX.a(selected,(byte)resist,eVi.rpY.d());
  if(selected.Wh(eVi.rpX.d())!=damage||selected.Wh(eVi.rpY.d())!=resist)throw new AssertionError("mask mismatch");
  vj binary=new vj();ByteBuffer buffer=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[1])));
  if(!binary.aG(buffer)||buffer.hasRemaining()||binary.afy==null||binary.afy.afH.agG!=damage||binary.afy.afH.agH!=resist)throw new AssertionError("binary mismatch");
  for(eVg element:foX.sNu)System.out.println(element.name()+" id="+element.aKg()+" damage="+element.fLC().aKg()+" resistance="+element.fLD().aKg());
  eWQ copy=new eWQ(ffw.shc);copy.b(eVR.j(new float[]{-1,0},1));copy.a(eVt.a(true,false,null));copy.C(null);
  if(copy.getValue()!=0)throw new AssertionError("copy without source");
  eWQ negative=new eWQ(ffw.shc);negative.b(eVR.j(new float[]{-2,0},1));negative.a(eVt.a(true,false,null));negative.C(null);
  if(negative.getValue()!=-2)throw new AssertionError("ordinary negative scalar");
  System.out.println("PASS kX56/le/vj/foX; masks="+damage+","+resist+"; empty-trigger copy=-1 ->0");
 }
}
