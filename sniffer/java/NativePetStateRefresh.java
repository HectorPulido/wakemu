/** Reconcile authoritative pet snapshots without abandoning native UI observers. */
public final class NativePetStateRefresh {
    private NativePetStateRefresh() {}
    private static final java.util.Map<Long, java.lang.ref.WeakReference<fvN>> PETS =
        new java.util.HashMap<>();

    public static fvH reconcile(fnR item, fvH incoming) {
        if (!(incoming instanceof fvN latest)) return incoming;
        aTx context = aTx.cWt();
        biB player = context == null ? null : context.cWu();
        fnR existing = player == null ? null : player.jE(item.LV());
        fvH registered = existing == null || existing == item || !existing.adO()
            ? null : existing.efH();
        return reconcileSnapshot(item.LV(), registered, latest);
    }

    static synchronized fvH reconcileSnapshot(long uid, fvH registered, fvN latest) {
        // Removal packets precede replacement snapshots, so registry lookup alone
        // can miss the object still observed by an open pet panel.
        PETS.entrySet().removeIf(entry -> entry.getValue().get() == null);
        java.lang.ref.WeakReference<fvN> cached = PETS.get(uid);
        fvH original = registered != null ? registered : cached == null ? null : cached.get();
        fvH result = reconcileState(original, latest);
        if (uid > 0 && result instanceof fvN pet) {
            PETS.put(uid, new java.lang.ref.WeakReference<>(pet));
        }
        return result;
    }

    static fvH reconcileState(fvH existing, fvN latest) {
        if (!(existing instanceof fvN original) || original == latest) return latest;
        // Use native mutators so bLK and actor observers receive their normal callbacks.
        original.setName(latest.getName());
        original.Yz(latest.agN());
        original.YA(latest.agJ());
        original.YB(latest.agL());
        original.mb(latest.agO());
        original.ad(latest.gpJ());
        original.ae(latest.gpV());
        original.ag(latest.gpL());
        original.Yy(latest.agU());
        return original;
    }

    public static void assignHydrated(fnR item, fvH incoming) {
        item.f(incoming);
    }
}
