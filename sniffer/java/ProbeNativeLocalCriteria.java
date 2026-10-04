import org.antlr.runtime.*;
import java.util.*;
public class ProbeNativeLocalCriteria {
 static alS parse(String s){eQd p=new eQd(new CommonTokenStream(new eQb(new ANTLRStringStream(s)))); ArrayList<alS> a=p.fGv(); if(p.getNumberOfSyntaxErrors()!=0)throw new AssertionError(s);return a.get(a.size()-1);}
 static void test(String s,boolean expected){alS p=parse(s); boolean b=((amb)p).b(null,null,null,null);if(b!=expected)throw new AssertionError(s+" => "+b);}
 public static void main(String[] args){
 test("cost = if (True) then (3) else (2); cost == 3",true);
 test("a = 1; b = a; a = 2; b == 1 and a == 2",true);
 test("n = 9223372036854775807; (n + 1) == (-9223372036854775807 - 1)",true);
 test("n = if (False) then (1) else if (True) then (2) else (3); n == 2",true);
 test("v = if (True) then (1) else (1.5); v == 1",true);
 System.out.println("PASS native local aliases bind prior expression trees; numeric conditional lazy; signed long overflow");
 }
}
