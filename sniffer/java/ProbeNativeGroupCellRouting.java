import java.lang.reflect.*;
/** Actual eYg and inherited bbA/bbB routing, preserving raw So(2). */
public class ProbeNativeGroupCellRouting {
 public static void main(String[]args)throws Exception {
  eGM.a(null);
  String[] runners={"eYg","eYr","eYv","eYt","eYn","eYm","eYw","eYs"};
  for(String runner:runners)for(int count:new int[]{2,3})for(float raw:new float[]{0,1,2,10}){
   eYg r=(eYg)Class.forName(runner).getConstructor().newInstance();
   eVv def=(eVv)Proxy.newProxyInstance(eVv.class.getClassLoader(),new Class[]{eVv.class},(o,m,a)->switch(m.getName()){
    case "fKJ"->count;case "So"->raw;default->throw new UnsupportedOperationException(m.getName());});
   ProbeNativeSummonDescriptor.set(r,"bfp",def);
   if(r.bbA()!=(count<3||raw==1)||r.bbB()!=(count>=3&&raw==0))throw new AssertionError(runner+" routing");
  }
  System.out.println("PASS native eYg +7 subclass routing matrices (64 cases)");
 }
}
