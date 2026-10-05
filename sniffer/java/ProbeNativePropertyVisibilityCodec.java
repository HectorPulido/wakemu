import java.nio.file.*;
/** Validate original eWt visibility additional namespace and current position. */
public class ProbeNativePropertyVisibilityCodec {
 public static void main(String[]args)throws Exception{
  cvY packet=new cvY();if(!packet.dp(Files.readAllBytes(Path.of(args[0])))||packet.eII()!=447)throw new AssertionError();
  eWt runner=new eWt();runner.lV(447);iN data=runner.ds(packet.eIJ());
  if(data==null||runner.getValue()!=5||!data.Qz())throw new AssertionError("visibility data");
  ij extra=data.QA();if(!extra.LW()||extra.LX().getX()!=2||extra.LX().getY()!=-3||extra.LX().NN()!=4||extra.Ma()!=3||!extra.MB())throw new AssertionError("position/direction/executed");
  System.out.println("PASS eWt visibility additional15position/16direction/33executed original decoder");
 }
}
