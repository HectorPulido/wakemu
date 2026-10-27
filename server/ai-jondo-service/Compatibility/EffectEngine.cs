using Jondo.Unity.World.Fights;
using Jondo.Unity.World.Maps;

namespace Jondo.Unity.Server.Managers;

public static class EffectEngine
{
    // Planner-private symbols from upstream, not raw native Wakfu IDs.
    public const int InvocaUnDoble=180, ColocaUnPortal=1181, ColocaUnaTrampa=400,
        ActivarBomba=1009, DesvelaLosInvisibles=202, ShieldPerLevel=1020, ShieldPerLife=1039;
    public const string AlLanzar="I", AlEmpezarElTurno="TB", AlAcabarElTurno="TE";
    public static string AlPonerseElEstado(int id) => "EON"+id;
    public static string AlActivarseElEstado(int id) => "EON"+id;
    public static string AlQuitarseElEstado(int id) => "EOFF"+id;
    internal enum SubCastAim { Candidate, ParentCaster, ParentCell, Nearest, Origin }
    internal readonly record struct SubCastRule(bool ByTheCandidate,bool ByTheOrigin,SubCastAim Aim,bool CappedByValue);
    internal static SubCastRule SubCastOf(int effect) => throw new NotSupportedException("Native sub-cast has not been projected");
    public static bool EsDeLaFamiliaDeSublanzar(int effect) => false;
    public static bool EsInvocacion(int effect) => effect is 181 or 1008 or 1011;
    public static bool EsMarcadorDeGuion(int effect) => false;
    public static bool CasterMeets(Fighter caster,SpellEffect row) => CasterQualifies(caster,row.TargetMask,null);
    public static bool CasterQualifies(Fighter caster,string? mask,Dictionary<Fighter,HashSet<int>>? states)
    {
        // Normalized rows only accept explicit side masks. Complex conditions
        // must be resolved/projected by native World instead of guessed here.
        return (mask ?? "").Split(',').All(t => t.Trim() is "" or "C" or "c" or "a" or "A");
    }
    public static bool CumpleLaMascara(Fighter caster,Fighter target,string mask)
    {
        var parts=mask.Split(',').Select(t=>t.Trim()).ToArray();
        return parts.Contains("C") || parts.Contains("c") ? target==caster
            : parts.Contains("a") ? target.TeamId==caster.TeamId
            : parts.Contains("A") ? target.TeamId!=caster.TeamId
            : false;
    }
    public static List<int> CasillasDelEfecto(SpellEffect row,int from,int aim,int direction=-1)
    {
        if(SemanticRows.DirectionalArea(row) is {} native)
        {
            if(!MapGeometry.IsValid(from)||!MapGeometry.IsValid(aim))return new();
            bool onCaster=SemanticRows.CenterOnCaster(row);
            var origin=MapGeometry.Context.Cells[onCaster?from:aim];
            return native.Forward(origin,MapGeometry.Context.Cells[onCaster?aim:from],direction)
                .Select(p=>MapGeometry.PointToCell(origin.X+p.Dx,origin.Y+p.Dy,origin.Z))
                .Where(c=>c>=0).Distinct().ToList();
        }
        if (SemanticRows.TryProjectedZone(row,SemanticRows.CenterOnCaster(row)?from:aim,out var cells)) return cells;
        if (row.Forma==';') return row.CeldasFijas.ToList();
        if (row.Forma is not ('P' or 'C' or '\0'))
            throw new NotSupportedException("Native zone shape has not been projected");
        return Enumerable.Range(0,MapGeometry.MaxCells)
            .Where(cell=>MapGeometry.Distance(aim,cell)<=row.Tamano
                         && MapGeometry.Distance(aim,cell)>=row.TamanoMinimo).ToList();
    }
    public static int DanoDeColision(int level,int push,int resistance,int cells) =>
        throw new NotSupportedException("Native collision damage has not been projected");
}
