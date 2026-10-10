import java.nio.*;
import java.nio.file.*;
/** Native title account ownership/preset/actor decoder regression. */
public class VerifyOwnedTitleComponents {
 public static void main(String[] args)throws Exception {
  int title=Integer.parseInt(args[3]);
  eST inventory=new eST();ByteBuffer account=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0])));
  inventory.a(7L,account);
  if(account.hasRemaining()||fn.pB.getNumber()!=7||inventory.E(fn.pB).stream().noneMatch(item -> item.AK()==title)||inventory.E(fn.pB).stream().anyMatch(item -> item.AK()==11431))throw new AssertionError("Wrong title ownership identity");
  if(!inventory.F(fn.pB).isEmpty())throw new AssertionError("Ownership incorrectly encoded as new flags");
  eSX presets=new eSX();ByteBuffer preset=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[1])));
  presets.a(7L,preset);
  if(preset.hasRemaining()||!presets.i(fn.pB,title).contains(1)||presets.qH(42L).isEmpty())throw new AssertionError("Wrong title preset identity");
  pq actor=new pq();ByteBuffer body=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[2])));
  if(!actor.aG(body)||body.hasRemaining()||Short.toUnsignedInt(actor.Tb.abs.abx)!=title)throw new AssertionError("Wrong active actor title");
  System.out.println("PASS native eST/eSX/pq account category7 title="+title+" source item11431 not owned as title");
 }
}
