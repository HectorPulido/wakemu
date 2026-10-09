/** Decode explicit synthetic collision payload using original client classes. */
public class VerifyCollisionTimeDatas {
 public static void main(String[]args) {
  iN data=iN.bf(java.util.HexFormat.of().parseHex(args[0]));
  if(!data.QG()||data.QH().Pk()!=0||!data.QH().MB())throw new AssertionError("Missing applied TimeDatas");
  if(data.QA().LT()!=2||data.QA().Mt()!=0||data.getValue()!=Integer.parseInt(args[1]))throw new AssertionError("Loss payload");
  System.out.println("Native collision iN TimeDatas status0/executedtrue and signed amount="+data.getValue());
 }
}
