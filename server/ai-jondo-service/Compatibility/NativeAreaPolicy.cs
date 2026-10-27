using System.Runtime.CompilerServices;
using Jondo.Unity.Server.Managers;

namespace Wakfu.Jondo;

/// <summary>Native recipient eligibility is independent of the cast aim.</summary>
internal static class NativeAreaPolicy
{
    private sealed record Policy(bool InArea);
    private static readonly ConditionalWeakTable<SpellEffect, Policy> Policies = new();
    public static void Bind(SpellEffect row, bool inArea) => Policies.Add(row, new Policy(inArea));
    public static bool InArea(SpellEffect row) => !Policies.TryGetValue(row, out var policy) || policy.InArea;
}
