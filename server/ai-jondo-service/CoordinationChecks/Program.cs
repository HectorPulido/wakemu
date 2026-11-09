using Wakfu.Jondo;
using System.Text.Json;
using Actor = Wakfu.Jondo.TeamCoordination.Actor;

void Check(bool actual, string message)
{
    if (!actual) throw new InvalidOperationException(message);
    Console.WriteLine("PASS " + message);
}

var target = new Actor(10, 2, 20);
Check(TeamCoordination.FocusValue(10, 1, target, target with { Hp = 10 }) == 0.5,
    "focus bonus is based on effective damage");
Check(TeamCoordination.FocusValue(10, 1, target, target with { Hp = -10 }) == 1,
    "lethal damage cannot count more than available health");
Check(TeamCoordination.FocusValue(10, 1, target, target with { Hp = 25 }) == 0,
    "healing an enemy does not receive a focus bonus");
var armored = target with { Armor = 12 };
Check(TeamCoordination.FocusValue(10, 1, armored, armored with { Armor = 2 }) == 0.5,
    "armor damage to the focused enemy receives the same bounded bonus");
Check(Math.Abs(TeamCoordination.FocusValue(10, 1, armored, armored with { Armor = 0, Hp = 15 }) - 0.85) < 1e-9,
    "damage across armor and health counts both actual losses");
Check(TeamCoordination.FocusValue(10, 1, armored, armored with { Armor = 20 }) == 0,
    "increasing enemy armor receives no focus bonus");
Check(TeamCoordination.FocusValue(11, 1, target, target with { Hp = 0 }) == 0,
    "damage to another enemy does not receive the focus bonus");
Check(TeamCoordination.FocusValue(10, 2, target, target with { Hp = 0 }) == 0,
    "an ally cannot be a focus target");
Check(TeamCoordination.FocusValue(10, 1, target with { Hp = 0 }, target with { Hp = 0 }) == 0,
    "a stale dead focus receives no bonus");
var reserved = new HashSet<(int, int)> { (1, 2) };
var clear = new[] { (0, 2) };
var blocking = new[] { (0, 2), (1, 2) };
Check(TeamCoordination.CorridorValue(reserved, clear, blocking, true) == -5,
    "ending with a footprint over a reserved native ray has a soft cost");
Check(TeamCoordination.CorridorValue(reserved, blocking, clear, true) == 5,
    "moving off a reserved ray has a soft reward");
Check(TeamCoordination.CorridorValue(reserved, blocking, blocking, true) == 0,
    "unchanged occupancy is not counted repeatedly");
Check(TeamCoordination.CorridorValue(reserved, clear, blocking, false) == 0,
    "an actor that does not block native LOS has no cost");

var visible = new Dictionary<long, Actor>
{
    [1] = new(1, 1, 100), [2] = new(2, 1, 100), [10] = target,
    [11] = new(11, 2, 0),
};
var cells = new[] { (0, 0), (1, 2), (1, 2) };
TeamCoordination.Context Read(string json)
{
    using var data = JsonDocument.Parse(json);
    return TeamCoordination.Read(data.RootElement, 1, 1, visible, cells);
}
var current = Read("""{"coordination":{"actorId":1,"team":1,"focusId":10,"actorBlocksNativeLos":true,"corridors":[{"ownerId":2,"targetId":10,"cells":[1,2]}]}}""");
Check(current.FocusId == 10 && current.BlocksLos == true && current.Reserved.SetEquals(new[] { (1, 2) }),
    "current visible focus and native corridor are projected to XY");
var hidden = Read("""{"coordination":{"actorId":1,"team":1,"focusId":99,"actorBlocksNativeLos":true,"corridors":[{"ownerId":2,"targetId":99,"cells":[1]}]}}""");
Check(hidden.FocusId == null && hidden.Reserved.Count == 0, "hidden or absent targets do not leak through advice");
var foreign = Read("""{"coordination":{"actorId":1,"team":3,"focusId":10,"actorBlocksNativeLos":true,"corridors":[{"ownerId":2,"targetId":10,"cells":[1]}]}}""");
Check(foreign.FocusId == null && foreign.Reserved.Count == 0 && foreign.BlocksLos == null, "foreign team context is ignored");
var malformed = Read("""{"coordination":{"actorId":1,"team":1,"focusId":10,"actorBlocksNativeLos":null,"corridors":[{"ownerId":2,"targetId":10,"cells":[1,"bad"]},{"ownerId":2,"targetId":11,"cells":[1]}]}}""");
Check(malformed.FocusId == 10 && malformed.Reserved.Count == 0 && malformed.BlocksLos == null,
    "malformed corridors and dead enemies are excluded without disabling valid focus");
Check(Read("""{"coordination":{"actorId":"bad","team":1}}""").FocusId == null,
    "malformed advisory authority cannot interrupt the turn");
