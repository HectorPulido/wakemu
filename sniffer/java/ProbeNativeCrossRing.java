import java.util.*;
public class ProbeNativeCrossRing {
 public static void main(String[] args) {
  any area=new any(); area.p(new int[]{3,1});
  Set<String> cells=new HashSet<>();
  for(int[] point:area.bEl()) cells.add(point[0]+","+point[1]);
  if(cells.size()!=12 || cells.contains("0,0") || cells.contains("1,1") || !cells.contains("0,-3")) throw new AssertionError(cells);
  area.p(new int[]{0,0});
  if(area.bEl().size()!=4) throw new AssertionError("Native list keeps four center duplicates");
  System.out.println("Native crossRing: swapped radii, 12 axial cells, center excluded; zero radius duplicates confirmed.");
 }
}
