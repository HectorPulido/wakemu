import java.lang.reflect.Proxy;
import java.util.ArrayList;

/** Offline native characteristic values, percentages and arithmetic. */
public class ProbeNumericConditions {
    static eHg actor(int current,int maximum) {
        return (eHg)Proxy.newProxyInstance(eHg.class.getClassLoader(),new Class<?>[]{eHg.class},
            (proxy,method,args)->switch(method.getName()) {
                case "a" -> true;
                case "c" -> current;
                case "d" -> maximum;
                default -> throw new UnsupportedOperationException(method.getName());
            });
    }
    static ArrayList<alS> parameters(String... strings) {
        ArrayList<alS> values=new ArrayList<>();
        for(String string:strings)values.add(new amc(string));
        return values;
    }
    public static void main(String[] args) {
        eHg caster=actor(81,101);
        System.out.println("HP="+new eJy(parameters("HP")).d(caster,null,null,null));
        System.out.println("HPpct="+new eJz(parameters("HP")).e(caster,null,null,null));
        System.out.println("HPpctTarget="+new eJz(parameters("HP","target")).e(caster,actor(50,100),null,null));
        alP left=new alw(3),right=new alw(2);
        System.out.println("sum="+alp.a(left,right).d(null,null,null,null));
        System.out.println("product="+alJ.a(left,right).d(null,null,null,null));
        System.out.println("difference="+amd.a(left,right).d(null,null,null,null));
        System.out.println("division="+alC.a(left,right).e(null,null,null,null));
    }
}
