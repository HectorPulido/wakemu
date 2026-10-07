import java.nio.file.*;import java.util.*;import java.lang.reflect.*;
public class VerifyPlantingRuntime {
 public static void main(String[] args)throws Exception{
  cyK start=new cyK();if(!start.dp(Files.readAllBytes(Path.of(args[0])))||start.eKk()!=1||start.eLS()!=2||start.eKl()!=7||start.Tz()!=3000||start.clx()!=47||start.cmG()!=74)throw new AssertionError("native planting start mismatch");
  cAx state=new cAx();if(!state.dp(Files.readAllBytes(Path.of(args[1])))||state.getX()!=10||state.getY()!=11||state.ejo()!=0)throw new AssertionError("native resource state mismatch");
  System.out.println("cyK12815 and cAx12782 native decoders verified");
  if(!Boolean.getBoolean("wakfu.verify.render"))return;
  Field unsafeField=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");unsafeField.setAccessible(true);sun.misc.Unsafe unsafe=(sun.misc.Unsafe)unsafeField.get(null);
  bOm resource=(bOm)unsafe.allocateInstance(bOm.class);EV deletion=new EV(){public Fg aJS(){return Fg.aAw;}};
  resource.g(new ArrayList<>(List.of(deletion)));if(!resource.eiU())throw new AssertionError("temporary own resource did not mark removal after forced native DELETE event");
  System.out.println("cyK12815 type2 mun1 own actor7 duration3000ms animation47; cAx12782 state0 decoded; forced bOm DELETE event flag verified independently (not end-to-end removal)");
 }
}
