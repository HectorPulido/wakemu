import java.nio.*;
import java.nio.file.*;
/** Offline native PET decoder and cosmetic accessory presence regression. */
public class VerifyMountCosmeticProjection {
 public static void main(String[] args) throws Exception {
  ByteBuffer input=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));
  rw pet=new rw();
  if(!pet.aG(input)||input.hasRemaining()||pet.Xl==null)throw new AssertionError("Invalid native PET");
  int[] actual={pet.Xl.Xp,pet.Xl.Xq,pet.Xl.Xr,pet.Xl.Xs,pet.Xl.Xt,pet.Xl.Xu};
  for(int i=0;i<6;i++)if(actual[i]!=Integer.parseInt(args[i+1]))throw new AssertionError("PET field "+i);
  fC cosmetic=fC.aw(Files.readAllBytes(Path.of(args[7])));
  if(cosmetic.AN()||cosmetic.AK()!=actual[2])throw new AssertionError("Accessory must be absent for native reference fallback");
  System.out.println("PASS native rw/rz projected skin="+actual[2]+" definition="+actual[0]+" accessory absent");
 }
}
