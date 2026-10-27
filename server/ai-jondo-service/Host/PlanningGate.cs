using System.Diagnostics;
using System.Text.Json;

namespace Wakfu.Jondo;

internal sealed record PlanningTiming(double ParseMs, double QueueWaitMs,
    double PlanningMs, double TotalMs);

internal sealed record PlanningGateResult(int Status, object Response, PlanningTiming Timing);

/// <summary>Serialize the shared core without granting queued work a fresh budget.</summary>
internal sealed class PlanningGate
{
    private readonly SemaphoreSlim core = new(1, 1);

    public static long Deadline(JsonElement request, long receivedTimestamp)
    {
        int budget = 2000;
        if (request.TryGetProperty("limits", out var limits)
            && limits.TryGetProperty("budgetMs", out var value))
            budget = Math.Clamp(value.GetInt32(), 1, 2000);
        return receivedTimestamp + (long)Math.Ceiling(budget * (Stopwatch.Frequency / 1000.0));
    }

    public async Task<PlanningGateResult> RunAsync(JsonElement request, long receivedTimestamp,
        Func<JsonElement, long, object> decide, CancellationToken cancellationToken = default)
    {
        double parseMs = Stopwatch.GetElapsedTime(receivedTimestamp).TotalMilliseconds;
        long queuedTimestamp = Stopwatch.GetTimestamp();
        double queueMs = 0, planningMs = 0;
        bool entered = false;
        int status;
        object response;
        try
        {
            long deadline = Deadline(request, receivedTimestamp);
            double remaining = Stopwatch.GetElapsedTime(Stopwatch.GetTimestamp(), deadline).TotalMilliseconds;
            cancellationToken.ThrowIfCancellationRequested();
            if (remaining < 1)
                throw new TimeoutException("Jondo decision deadline reached before admission");
            entered = await core.WaitAsync(TimeSpan.FromMilliseconds(remaining), cancellationToken);
            queueMs = Stopwatch.GetElapsedTime(queuedTimestamp).TotalMilliseconds;
            cancellationToken.ThrowIfCancellationRequested();
            if (!entered || Stopwatch.GetTimestamp() >= deadline)
                throw new TimeoutException("Jondo decision deadline reached in queue");
            long planningTimestamp = Stopwatch.GetTimestamp();
            try
            {
                response = decide(request, deadline);
            }
            finally
            {
                planningMs = Stopwatch.GetElapsedTime(planningTimestamp).TotalMilliseconds;
            }
            cancellationToken.ThrowIfCancellationRequested();
            if (Stopwatch.GetTimestamp() >= deadline)
                throw new TimeoutException("Jondo decision completed after its deadline");
            status = 200;
        }
        catch (Exception error) when (error is TimeoutException or OperationCanceledException)
        {
            status = 503;
            response = new { error = error.Message, errorType = error.GetType().Name };
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException
            or KeyNotFoundException or NotSupportedException or FormatException or OverflowException)
        {
            status = 400;
            response = new { error = error.Message, errorType = error.GetType().Name };
        }
        finally
        {
            if (entered) core.Release();
            if (planningMs == 0)
                queueMs = Stopwatch.GetElapsedTime(queuedTimestamp).TotalMilliseconds;
        }
        return new PlanningGateResult(status, response, new PlanningTiming(parseMs, queueMs,
            planningMs, Stopwatch.GetElapsedTime(receivedTimestamp).TotalMilliseconds));
    }
}
