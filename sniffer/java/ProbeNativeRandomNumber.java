import java.util.*;
public class ProbeNativeRandomNumber {
 static eLb expression(long limit,Long...excluded){ArrayList<alS> a=new ArrayList<>();a.add(new alw(limit));if(excluded.length>0){ArrayList<alS> values=new ArrayList<>();for(long n:excluded)values.add(new alw(n));a.add(new alx(values));}return new eLb(a);}
 static void fail(eLb e){try{e.d(null,null,null,null);throw new AssertionError("accepted empty/invalid range");}catch(IllegalArgumentException|alA expected){System.out.println("PASS invalid/empty: "+expected.getClass().getSimpleName());}}
 public static void main(String[]args){
  if(expression(1).d(null,null,null,null)!=0)throw new AssertionError();
  if(expression(5,0L,1L,3L,4L,4L,-1L,8L).d(null,null,null,null)!=2)throw new AssertionError();
  Set<Long>s=new HashSet<>();for(int i=0;i<1000;i++){long n=expression(6,1L,3L).d(null,null,null,null);if(!List.of(0L,2L,4L,5L).contains(n))throw new AssertionError();s.add(n);}if(s.size()!=4)throw new AssertionError();
  System.out.println("PASS singleton/exclusions/candidate support");fail(expression(0));fail(expression(-1));fail(expression(2,0L,1L));
 }
}
