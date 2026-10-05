import java.util.*;
public class ProbeNativeRectangleRing {
 public static void main(String[] args) {
  for(int[] bounds:new int[][]{{1,1},{0,0},{1,0,2,3},{2,1}}){
   anF area=new anF();area.p(bounds);
   System.out.print(area.bEn()+":");
   for(int[] p:area.bEl())System.out.print(Arrays.toString(p));
   System.out.println();
  }
 }
}
