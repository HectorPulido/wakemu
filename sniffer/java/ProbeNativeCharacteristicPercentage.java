/** Native eJz/GS.B percentage oracle; no combat runtime or service access. */
public class ProbeNativeCharacteristicPercentage {
    public static void main(String[] args) {
        int[][] cases = {{0,0}, {1,0}, {-1,0}, {1,3}, {-1,3},
                         {1,-3}, {Integer.MAX_VALUE,1}, {Integer.MIN_VALUE,1}};
        int[] expected = {-1,Integer.MAX_VALUE,Integer.MAX_VALUE,33,-34,-34,
                          Integer.MAX_VALUE,Integer.MAX_VALUE};
        for (int index=0; index<cases.length; index++) {
            int current=cases[index][0], maximum=cases[index][1];
            int actual=GS.B((float)current/(float)maximum*100.0f);
            if (actual!=expected[index]) throw new AssertionError(
                current+"/"+maximum+" native="+actual+" expected="+expected[index]);
        }
        System.out.println("PASS native eJz/GS.B percentage: "+cases.length+" cases");
    }
}
