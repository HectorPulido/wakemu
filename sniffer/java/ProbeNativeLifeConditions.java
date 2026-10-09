import java.lang.reflect.Field;
import java.util.*;
import com.google.gson.Gson;

/** Actual eNJ/eOe resolve separate eGj.dsA and eHg.baF boolean facts. */
public class ProbeNativeLifeConditions {
    static class Actor extends ProbeNativeTargetLifeSelectors.Actor {
        boolean dead;
        public boolean dsA(){return dead;}
    }
    static class Area extends ProbeNativeTargetAreaOwnerSelectors.Area {
        boolean inPlay;
        public boolean baF(){return inPlay;}
    }
    static ArrayList<alS> arguments(String selector) {
        ArrayList<alS> values=new ArrayList<>();
        if(selector!=null)values.add(new amc(selector));return values;
    }
    public static void main(String[] args)throws Exception {
        Field singleton=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");singleton.setAccessible(true);
        sun.misc.Unsafe unsafe=(sun.misc.Unsafe)singleton.get(null);
        Actor source=(Actor)unsafe.allocateInstance(Actor.class),target=(Actor)unsafe.allocateInstance(Actor.class);
        Area area=(Area)unsafe.allocateInstance(Area.class);
        List<Object> rows=new ArrayList<>();
        source.dead=false;source.alive=true;
        for(boolean dead:new boolean[]{false,true})for(boolean inPlay:new boolean[]{false,true}) {
            target.dead=dead;target.alive=inPlay;
            for(String selector:new String[]{null,"caster","target","TARGET","other"}) {
                boolean targetSelected=selector!=null&&selector.equalsIgnoreCase("target");
                String actualDead=Integer.toString(new eNJ(arguments(selector)).a(source,target,null,null));
                String actualPlay=Integer.toString(new eOe(arguments(selector)).a(source,target,null,null));
                if(!actualDead.equals((targetSelected?dead:source.dead)?"0":"-1")
                    ||!actualPlay.equals((targetSelected?inPlay:source.alive)?"0":"-1"))throw new AssertionError("actor life");
                rows.add(Arrays.asList(dead,inPlay,selector,actualDead,actualPlay));
            }
        }
        List<Object> areaRows=new ArrayList<>();
        for(boolean inPlay:new boolean[]{false,true}) {
            area.inPlay=inPlay;
            int dead=new eNJ(arguments("target")).a(source,area,null,null);
            int play=new eOe(arguments("target")).a(source,area,null,null);
            if(dead!=-1||play!=(inPlay?0:-1))throw new AssertionError("actual faV type");
            areaRows.add(Arrays.asList(inPlay,dead,play));
        }
        if(new eNJ(arguments("target")).a(source,null,null,null)!=-1
            ||new eOe(arguments("target")).a(source,null,null,null)!=-1)throw new AssertionError("native null");
        System.out.println(new Gson().toJson(Map.of("schema","native-life-conditions-v1","actors",rows,"areas",areaRows,"null_false",true)));
    }
}
