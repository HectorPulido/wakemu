/** aiL setMobileLookAt branches; NONE handled by binding, not aBz.bo. */
public class ProbeNativeCastFacing {
 public static void main(String[] args) {
  int[] inputs={-2147483648,-100,-5,-2,-1,0,1,2,5,100,2147483647};
  for(int dx:inputs)for(int dy:inputs){
   aAS cardinal=new aBA(dx,dy,0).bXz();
   aAS diagonal=(dx==0&&dy==0)?aAS.dyD:aBA.bo((float)dx,(float)dy);
   System.out.println(dx+"\t"+dy+"\t"+cardinal.wp()+"\t"+diagonal.wp());
  }
 }
}
