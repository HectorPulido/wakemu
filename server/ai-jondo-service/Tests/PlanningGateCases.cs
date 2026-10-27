using System.Diagnostics;
using System.Text.Json;
using Wakfu.Jondo;

internal static class PlanningGateCases
{
    public static int Run() => RunAsync().GetAwaiter().GetResult();

    private static JsonElement Request(int budget) => JsonSerializer.SerializeToElement(new
    {
        protocol = 1, limits = new { budgetMs = budget },
    });

    private static async Task<int> RunAsync()
    {
        int checks = 0;
        void Check(bool value, string name)
        {
            if (!value) throw new Exception("FAIL: " + name);
            checks++;
            Console.WriteLine("PASS: " + name);
        }
        var gate = new PlanningGate();
        int calls = 0;
        var expired = await gate.RunAsync(Request(1), Stopwatch.GetTimestamp() - Stopwatch.Frequency,
            (_, _) => { calls++; return new { action = "unexpected" }; });
        Check(expired.Status == 503 && calls == 0 && expired.Timing.PlanningMs == 0,
            "time already spent parsing cannot be granted again to the planner");
        using (var cancelled = new CancellationTokenSource())
        {
            cancelled.Cancel();
            var result = await gate.RunAsync(Request(1000), Stopwatch.GetTimestamp(),
                (_, _) => { calls++; return new { action = "unexpected" }; }, cancelled.Token);
            Check(result.Status == 503 && calls == 0,
                "cancelled decision never enters the shared core");
        }
        var invalid = await gate.RunAsync(JsonSerializer.SerializeToElement(new
            { limits = new { budgetMs = "invalid" } }), Stopwatch.GetTimestamp(),
            (_, _) => { calls++; return new { action = "unexpected" }; });
        Check(invalid.Status == 400 && calls == 0,
            "invalid decision budgets do not acquire or poison the core gate");

        var entered = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        using var release = new ManualResetEventSlim();
        int active = 0, maximumActive = 0, executed = 0;
        var first = Task.Run(() => gate.RunAsync(Request(2000), Stopwatch.GetTimestamp(), (_, _) =>
        {
            int count = Interlocked.Increment(ref active);
            maximumActive = Math.Max(maximumActive, count);
            Interlocked.Increment(ref executed);
            entered.SetResult();
            if (!release.Wait(TimeSpan.FromSeconds(5))) throw new Exception("Test core was not released");
            Interlocked.Decrement(ref active);
            return new { action = "first" };
        }));
        await entered.Task.WaitAsync(TimeSpan.FromSeconds(5));
        try
        {
            using var queuedCancellation = new CancellationTokenSource();
            var cancelledQueued = gate.RunAsync(Request(1000), Stopwatch.GetTimestamp(),
                (_, _) => { Interlocked.Increment(ref executed); return new { action = "cancelled" }; },
                queuedCancellation.Token);
            queuedCancellation.Cancel();
            var cancelledResult = await cancelledQueued;
            Check(cancelledResult.Status == 503 && executed == 1 && cancelledResult.Timing.PlanningMs == 0,
                "cancellation while queued never executes the abandoned callback");
            var queued = Enumerable.Range(0, 3).Select(_ => gate.RunAsync(Request(20),
                Stopwatch.GetTimestamp(), (_, _) =>
                {
                    Interlocked.Increment(ref executed);
                    return new { action = "expired" };
                })).ToArray();
            var results = await Task.WhenAll(queued).WaitAsync(TimeSpan.FromSeconds(5));
            Check(results.All(row => row.Status == 503) && executed == 1,
                "queued decisions expire without executing after the current owner releases");
            Check(results.All(row => row.Timing.QueueWaitMs > 0 && row.Timing.PlanningMs == 0
                && row.Timing.TotalMs >= row.Timing.QueueWaitMs),
                "queue expiry records waiting separately from planner execution");
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                kind = "planning_gate_controlled_load", heldOwners = 1, queuedRequests = results.Length,
                queuedBudgetMs = 20, expiredBeforeOwnerRelease = results.Length,
                executedCallbacks = executed,
                queueWaitMs = results.Select(row => row.Timing.QueueWaitMs).ToArray(),
                totalMs = results.Select(row => row.Timing.TotalMs).ToArray(),
                scope = "actual gate with controlled callback; not a native encounter benchmark",
            }));
        }
        finally { release.Set(); }
        Check((await first).Status == 200 && maximumActive == 1,
            "the original core owner remains serialized and completes normally");

        long received = Stopwatch.GetTimestamp();
        long forwardedDeadline = 0;
        var healthy = await gate.RunAsync(Request(1000), received, (_, deadline) =>
        {
            forwardedDeadline = deadline;
            return new { action = "healthy" };
        });
        Check(healthy.Status == 200 && forwardedDeadline == PlanningGate.Deadline(Request(1000), received),
            "planner receives the original absolute deadline rather than a renewed budget");
        var failure = await gate.RunAsync(Request(1000), Stopwatch.GetTimestamp(),
            (_, _) => throw new ArgumentException("Invalid source"));
        Check(failure.Status == 400, "a failed planner returns a bounded source error");
        var afterFailure = await gate.RunAsync(Request(1000), Stopwatch.GetTimestamp(),
            (_, _) => new { action = "released" });
        Check(afterFailure.Status == 200, "planner errors always release the serialized core");
        var late = await gate.RunAsync(Request(1000), Stopwatch.GetTimestamp(), (_, _) =>
            throw new TimeoutException("Cooperative planner deadline"));
        Check(late.Status == 503, "cooperative planner expiry never returns an adoptable decision");
        var completedLate = await gate.RunAsync(Request(20), Stopwatch.GetTimestamp(), (_, _) =>
        {
            Thread.Sleep(30);
            return new { action = "too_late" };
        });
        Check(completedLate.Status == 503 && completedLate.Timing.PlanningMs > 0,
            "an opaque callback returning after its deadline is discarded before publication");
        return checks;
    }
}
