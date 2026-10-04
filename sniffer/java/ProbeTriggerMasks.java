import java.util.BitSet;

/** Native Qi channel routing, no actor, service, data catalog or fight required. */
public class ProbeTriggerMasks {
    static class Runner extends eYg {
        final int index;
        Runner(int index) { this.index=index; }
        BitSet mask(int i) { BitSet b=new BitSet();if(i==index)b.set(71);return b; }
        @Override public BitSet aZG(){return mask(0);}
        @Override public BitSet aZH(){return mask(1);}
        @Override public BitSet aZI(){return mask(2);}
        @Override public BitSet aZJ(){return mask(3);}
        @Override public BitSet bbu(){return mask(4);}
        @Override public BitSet bbv(){return mask(5);}
    }
    static class Matcher extends Qi {
        Matcher(){super(null);}
        @Override protected boolean b(BitSet bits,Qe source,byte channel){return false;}
        @Override protected void a(Qe source,byte channel){}
        void test(int index,int channel,boolean alternate) {
            bgr.clear();bgs.clear();bgt.clear();
            BitSet bits=new BitSet();bits.set(71);
            boolean result=alternate?b(bits,(byte)channel,new Runner(index)):a(bits,(byte)channel,new Runner(index));
            System.out.println("index="+index+" channel="+channel+" matched="+result+" apply="+bgr.size()+" remove="+bgs.size());
        }
    }
    public static void main(String[] args) {
        Matcher matcher=new Matcher();
        int[][] standard={{0,1},{1,2},{3,3},{2,4},{4,5},{5,6}};
        for(int[] pair:standard) matcher.test(pair[0],pair[1],false);
        int[][] alternate={{0,10},{1,20},{3,30},{2,40},{5,60},{4,50}};
        for(int[] pair:alternate) matcher.test(pair[0],pair[1],true);
    }
}
