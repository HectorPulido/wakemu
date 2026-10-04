import java.lang.reflect.Proxy;
import java.util.ArrayList;

/** Offline direct eJQ predicate using native alb proxies and aBn cells. */
public class ProbeCriterionDistance {
    static alb actor(int x,int y,byte radius) {
        return (alb)Proxy.newProxyInstance(alb.class.getClassLoader(),new Class<?>[]{alb.class},
            (proxy,method,args)->switch(method.getName()) {
                case "bcz" -> x;
                case "bcA" -> y;
                case "bcL" -> radius;
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }
    public static void main(String[] args) {
        eJQ condition = new eJQ(new ArrayList<alS>());
        alb caster=actor(0,0,(byte)1);
        System.out.println("actor_diagonal_radius1="+condition.d(caster,actor(3,3,(byte)1),null,null));
        System.out.println("actor_axis_clamp="+condition.d(caster,actor(1,4,(byte)1),null,null));
        System.out.println("cell_radius1="+condition.d(caster,new aBn(3,3,(short)999),null,null));
        System.out.println("null_target="+condition.d(caster,null,null,null));
        System.out.println("null_caster="+condition.d(null,new aBn(3,3,(short)999),null,null));
    }
}
