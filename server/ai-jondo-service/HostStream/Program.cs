using System.Diagnostics;
using System.Text.Json;
using Wakfu.Jondo;

// One protocol request per line; an isolated diagnostic host, not a server.
var gate = new PlanningGate();
while (await Console.In.ReadLineAsync() is { } line)
{
    try
    {
        using var input = JsonDocument.Parse(line);
        var result = await gate.RunAsync(input.RootElement, Stopwatch.GetTimestamp(),
            (payload, deadline) => Planner.Decide(payload, deadline));
        Console.WriteLine(JsonSerializer.Serialize(new { status = result.Status, response = result.Response }));
    }
    catch (Exception error)
    {
        Console.WriteLine(JsonSerializer.Serialize(new { status = 500, error = error.GetType().Name }));
    }
}
