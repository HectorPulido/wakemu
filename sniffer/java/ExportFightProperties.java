/** Export actual native PE IDs; names are original client enum symbols. */
public class ExportFightProperties {
 public static void main(String[]args) {
  System.out.println("{\"source\":\"ffe / PE.aKg\",\"properties\":[");
  boolean first=true;
  for(ffe p:ffe.values()) {
   if(!first)System.out.println(",");first=false;
   String branch=p==ffe.seh?"insert_extra_turn_current_round":p==ffe.sdH?"timeline_recalculate":
    p==ffe.seb?"set_ap_minimum":p==ffe.see?"set_mp_minimum":p==ffe.sdV?"notify_wp_listeners":
    p==ffe.sdC||p==ffe.sdO?"occupancy_and_position":"counter";
   System.out.print("{\"id\":"+p.aKg()+",\"symbol\":\""+p.name()+
    "\",\"category\":"+p.aZu()+",\"application_branch\":\""+branch+"\"}");
  }
  System.out.println("\n]}");
 }
}
