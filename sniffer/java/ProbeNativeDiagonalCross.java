import java.util.Arrays;
/** Native anx definitions, serialized descriptions and anc membership. */
public class ProbeNativeDiagonalCross {
    public static void main(String[] args) {
        for (int[] params : new int[][]{{1},{2,1},{1,2,3,4},{0},{-1}}) {
            anx area = new anx(); area.p(params);
            System.out.print("parameters="+Arrays.toString(params)+" native="+area.bEm()+" isotropic="+area.bEj()+" offsets=");
            for(int[] cell:area.bEl()) System.out.print(Arrays.toString(cell));
            System.out.println();
            for(int direction=0;direction<8;direction++) {
                for(int x=-5;x<=5;x++) for(int y=-5;y<=5;y++) {
                    final int xx=x,yy=y;
                    boolean expected=area.bEl().stream().anyMatch(c->c[0]==xx&&c[1]==yy);
                    boolean actual=area.a(0,0,(short)3,3,0,(short)9,aAS.wL(direction),x,y,(short)20);
                    if(expected!=actual) throw new AssertionError("direction changes isotropic area");
                }
            }
        }
        System.out.println("PASS native anx point lists; descriptions;8 orientations; arbitrary Z");
    }
}
