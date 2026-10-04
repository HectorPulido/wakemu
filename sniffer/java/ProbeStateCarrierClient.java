/** Offline aTR callback: incoming state runner is observed, not executed. */
public class ProbeStateCarrierClient {
    static class State extends eZk {
        int execution,notifications;
        @Override protected void c(Qe parent,boolean flag){execution++;}
        @Override public boolean Ty(){return false;}
        @Override public boolean bbW(){return false;}
        @Override public void bbE(){notifications++;}
        @Override public void fSn(){}
    }
    static class Action extends aTR {
        Action(State state){super(0,0,0,310,state);}
        void observe(){super.cbj();}
    }
    public static void main(String[] args){
        State state=new State();state.bbr();
        if(!state.bbs())throw new AssertionError("native bbr");
        // Exact runner operation performed by aTR.cby before its callback.
        state.bbq();
        new Action(state).observe();
        if(state.bbs() || state.execution!=0 || state.notifications!=1)
            throw new AssertionError("incoming carrier executed gameplay");
        System.out.println("aTR.cbj: bbs=false, gameplay calls=0, observer calls=1");
    }
}
