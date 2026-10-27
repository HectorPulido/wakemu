using System.Buffers.Binary;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;

namespace Wakfu.Jondo;

internal static class Program
{
    private const int MaxFrame = 4 * 1024 * 1024;
    private static readonly SemaphoreSlim Connections = new(64);
    private static readonly SemaphoreSlim Decisions = new(8);
    private static readonly PlanningGate Planning = new();

    public static async Task Main(string[] args)
    {
        if (args.Contains("--health"))
        {
            using var peer = new TcpClient();
            using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            await peer.ConnectAsync("127.0.0.1", int.Parse(Environment.GetEnvironmentVariable("WAKFU_JONDO_PORT") ?? "8091"), deadline.Token);
            using var channel = peer.GetStream();
            byte[] payload = JsonSerializer.SerializeToUtf8Bytes(new { id = 1, endpoint = "/health", payload = new { } });
            byte[] header = new byte[4]; BinaryPrimitives.WriteInt32BigEndian(header, payload.Length);
            await channel.WriteAsync(header, deadline.Token); await channel.WriteAsync(payload, deadline.Token);
            await channel.ReadExactlyAsync(header, deadline.Token);
            int length = BinaryPrimitives.ReadInt32BigEndian(header);
            if (length <= 0 || length > MaxFrame) throw new IOException("Invalid health response");
            byte[] response = new byte[length]; await channel.ReadExactlyAsync(response, deadline.Token);
            using var document = JsonDocument.Parse(response);
            if (document.RootElement.GetProperty("status").GetInt32() != 200) throw new IOException("Jondo is not ready");
            Console.WriteLine("healthy"); return;
        }
        if (args.Contains("--once"))
        {
            using var request = JsonDocument.Parse(await Console.In.ReadToEndAsync());
            Console.WriteLine(JsonSerializer.Serialize(Planner.Decide(request.RootElement)));
            return;
        }
        int port = int.Parse(Environment.GetEnvironmentVariable("WAKFU_JONDO_PORT") ?? "8091");
        var bind = IPAddress.Parse(Environment.GetEnvironmentVariable("WAKFU_JONDO_BIND") ?? "127.0.0.1");
        var listener = new TcpListener(bind, port);
        listener.Start(64);
        Console.WriteLine(JsonSerializer.Serialize(new { eventName = "jondo_ready", port, transport = "tcp", upstream = Planner.Upstream }));
        while (true)
        {
            var client = await listener.AcceptTcpClientAsync();
            if (!Connections.Wait(0)) { client.Dispose(); continue; }
            _ = Task.Run(async () =>
            {
                try { await Serve(client); }
                catch (Exception e) when (e is IOException or SocketException or JsonException or ArgumentException or OperationCanceledException) { }
                finally { client.Dispose(); Connections.Release(); }
            });
        }
    }

    private static async Task Serve(TcpClient client)
    {
        client.NoDelay = true;
        using var stream = client.GetStream();
        long previous = 0;
        while (true)
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            byte[] header = new byte[4];
            await stream.ReadExactlyAsync(header, timeout.Token);
            int length = BinaryPrimitives.ReadInt32BigEndian(header);
            if (length <= 0 || length > MaxFrame) return;
            byte[] bytes = new byte[length];
            await stream.ReadExactlyAsync(bytes, timeout.Token);
            long receivedTimestamp = Stopwatch.GetTimestamp();
            using var document = JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 64 });
            var frame = document.RootElement;
            UniqueKeys(frame);
            long id = frame.GetProperty("id").GetInt64();
            if (id <= previous || frame.EnumerateObject().Count() != 3) return;
            previous = id;
            string endpoint = frame.GetProperty("endpoint").GetString() ?? "";
            var request = frame.GetProperty("payload");
            int status;
            object response;
            PlanningTiming? serviceTiming = null;
            if (endpoint == "/health")
            {
                status = 200;
                response = new { status = "ok", service = "wakfu-ai-jondo", transport = "tcp", protocols = new[] { 1 }, upstream = Planner.Upstream };
            }
            else if (endpoint != "/jondo/decide")
            {
                status = 404; response = new { error = "Unknown Jondo endpoint" };
            }
            else if (!Decisions.Wait(0))
            {
                status = 503; response = new { error = "Jondo decision capacity reached" };
                double elapsed = Stopwatch.GetElapsedTime(receivedTimestamp).TotalMilliseconds;
                serviceTiming = new PlanningTiming(elapsed, 0, 0, elapsed);
            }
            else
            {
                try
                {
                    var result = await Planning.RunAsync(request, receivedTimestamp,
                        (payload, deadline) => Planner.Decide(payload, deadlineTimestamp: deadline), timeout.Token);
                    response = result.Response;
                    status = result.Status;
                    serviceTiming = result.Timing;
                }
                finally { Decisions.Release(); }
            }
            if (serviceTiming != null)
            {
                var measured = JsonSerializer.SerializeToNode(response)!.AsObject();
                measured["serviceTiming"] = JsonSerializer.SerializeToNode(new
                {
                    parseMs = serviceTiming.ParseMs,
                    queueWaitMs = serviceTiming.QueueWaitMs,
                    planningMs = serviceTiming.PlanningMs,
                    totalMs = serviceTiming.TotalMs,
                    scope = "received_frame_to_completed_decision",
                });
                response = measured;
            }
            byte[] reply = JsonSerializer.SerializeToUtf8Bytes(new { id, status, payload = response });
            if (reply.Length > MaxFrame) return;
            BinaryPrimitives.WriteInt32BigEndian(header, reply.Length);
            await stream.WriteAsync(header, timeout.Token);
            await stream.WriteAsync(reply, timeout.Token);
        }
    }

    private static void UniqueKeys(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            var seen = new HashSet<string>();
            foreach (var property in value.EnumerateObject())
            {
                if (!seen.Add(property.Name)) throw new JsonException("Duplicate JSON key");
                UniqueKeys(property.Value);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
            foreach (var child in value.EnumerateArray()) UniqueKeys(child);
    }
}
