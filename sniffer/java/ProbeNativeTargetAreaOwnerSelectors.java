import java.lang.reflect.Field;
import java.util.*;
import com.google.gson.Gson;

/** fcE bit44 actual non-summon eGj; bit46 direct Qq source owner identity. */
public class ProbeNativeTargetAreaOwnerSelectors {
    static class Actor extends ProbeNativeTargetLifeSelectors.Actor {
        boolean summon;
        public boolean dTE(){return summon;}
    }
    static class Area extends faX {
        PV owner;
        public void aQc(){}
        protected Qq bcs(){return this;}
        public void a(int x,int y,short z,Qe trigger){}
        public java.util.List<amP> d(amP target){return null;}
        public PV bch(){return owner;}
        public boolean bEe(){return true;}
        public boolean bcR(){return true;}
    }
    public static void main(String[] args)throws Exception {
        Field singleton=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");singleton.setAccessible(true);
        sun.misc.Unsafe unsafe=(sun.misc.Unsafe)singleton.get(null);
        Actor source=(Actor)unsafe.allocateInstance(Actor.class), target=(Actor)unsafe.allocateInstance(Actor.class);
        source.identity=1;target.identity=2;
        Area area=(Area)unsafe.allocateInstance(Area.class);
        List<Object> rows=new ArrayList<>();
        for(boolean summon:new boolean[]{false,true})for(boolean owned:new boolean[]{false,true}) {
            target.summon=summon;area.owner=owned?target:source;
            for(long mask:new long[]{1L<<44,1L<<46,(1L<<44)|(1L<<46),32|(1L<<44),(1L<<47)|(1L<<46)}) {
                String result=fcE.j(new long[]{mask}).a(target,area).toString();
                boolean expected=(!( (mask&(1L<<44))!=0) || !summon)
                    && (!( (mask&(1L<<46))!=0) || owned)
                    && ((mask&32)==0 || summon);
                if(!result.equals(expected?"VALID":"INVALID"))throw new AssertionError(result);
                rows.add(Arrays.asList(summon,owned,mask,result));
            }
        }
        for(long mask:new long[]{1L<<44,1L<<46}) {
            if(!fcE.j(new long[]{mask}).a(area,source).toString().equals("INVALID"))
                throw new AssertionError("Native type guard");
        }
        area.owner=null;
        if(!fcE.j(new long[]{1L<<46}).a(target,area).toString().equals("INVALID"))
            throw new AssertionError("Native null owner");
        System.out.println(new Gson().toJson(Map.of("schema","native-target-area-owner-v1","cases",rows,"nonfighter_target_rejected",true,"nonarea_source_rejected",true,"null_owner_rejected",true)));
    }
}
