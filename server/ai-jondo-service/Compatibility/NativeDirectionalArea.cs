using Jondo.Unity.World.Maps;
using System.Text.Json;

namespace Jondo.Unity.Server.Managers;

/// <summary>Native anc forward enumeration and ana transpose membership.</summary>
internal sealed class NativeDirectionalArea
{
    internal IReadOnlyList<(int Dx,int Dy)> Raw { get; }
    internal bool UseTargetRadius { get; }
    internal bool CenterOnCaster { get; }
    private readonly HashSet<(int,int)> points;
    private static readonly (int,int)[] Directions =
        { (1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1) };

    internal NativeDirectionalArea(IReadOnlyList<(int Dx,int Dy)> raw,bool useTargetRadius,bool centerOnCaster=false)
    {
        Raw=Array.AsReadOnly(raw.ToArray());points=Raw.ToHashSet();UseTargetRadius=useTargetRadius;CenterOnCaster=centerOnCaster;
    }

    internal static NativeDirectionalArea Parse(JsonElement descriptor)
    {
        if(!descriptor.TryGetProperty("version",out var version)||version.GetInt32()!=1
            ||!descriptor.TryGetProperty("isotropic",out var isotropic)||isotropic.ValueKind!=JsonValueKind.False
            ||!descriptor.TryGetProperty("useTargetRadius",out var radius)
            ||radius.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
            ||!descriptor.TryGetProperty("centerOnCaster",out var center)
            ||center.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
            ||center.GetBoolean()==radius.GetBoolean())
            throw new ArgumentException("Invalid native directional area contract");
        var raw=descriptor.GetProperty("rawOffsets").EnumerateArray().Select(p=>
        {
            if(p.GetArrayLength()!=2)throw new ArgumentException("Directional offsets require XY");
            return(Dx:p[0].GetInt32(),Dy:p[1].GetInt32());
        }).ToArray();
        return new NativeDirectionalArea(raw,radius.GetBoolean(),center.GetBoolean());
    }

    internal static bool Rotation(CellXYZ origin,CellXYZ reference,int direction,out (int Dx,int Dy) rotation)
    {
        float dx=(float)((double)origin.X-reference.X),dy=(float)((double)origin.Y-reference.Y);
        if(dx==0&&dy==0)
        {
            rotation=direction is >=0 and <8?Directions[direction]:default;
            return direction is >=0 and <8;
        }
        float angle=-(float)Math.Atan2(dy,dx);
        rotation=angle>=(float)(Math.PI/4)&&angle<(float)(3*Math.PI/4)?(0,-1)
            :angle>=(float)(-Math.PI/4)&&angle<(float)(Math.PI/4)?(1,0)
            :angle>=(float)(-3*Math.PI/4)&&angle<(float)(-Math.PI/4)?(0,1):(-1,0);
        return true;
    }

    internal static int DirectionAfterPath(MonsterTactics.Board board,IReadOnlyList<int> path,int currentDirection)
    {
        int direction=currentDirection;
        for(int i=1;i<path.Count;i++)
        {
            // Native gate travel preserves facing; an unrecognized long jump
            // has no walking-facing authority and defers coincident-area casts.
            if(board.IsPortalTravel(path[i-1],path[i])
                ||MapGeometry.TryPortalRoute(path[i-1],out var gate)&&gate.To==path[i])continue;
            var from=MapGeometry.Context.Cells[path[i-1]];var to=MapGeometry.Context.Cells[path[i]];
            long dx=(long)to.X-from.X,dy=(long)to.Y-from.Y;
            if(dx==0&&dy==0)continue;
            direction=-1;
            for(int index=0;index<Directions.Length;index++)
                if(Directions[index].Item1==dx&&Directions[index].Item2==dy){direction=index;break;}
        }
        return direction;
    }

    internal IReadOnlyList<(int Dx,int Dy)> Forward(CellXYZ origin,CellXYZ reference,int direction)
    {
        if(!Rotation(origin,reference,direction,out var r))return Array.Empty<(int,int)>();
        return Raw.Select(p=>(r.Dx*p.Dx-r.Dy*p.Dy,r.Dy*p.Dx+r.Dx*p.Dy)).Distinct().ToArray();
    }

    internal bool Contains(CellXYZ origin,CellXYZ reference,int direction,CellXYZ point,int radius)
    {
        if(!Rotation(origin,reference,direction,out var r))return false;
        if(radius is <-128 or >127)return false;
        radius=Math.Max(0,radius);
        long x=(long)point.X-origin.X,y=(long)point.Y-origin.Y;
        long localX=r.Dx*x+r.Dy*y,localY=-r.Dy*x+r.Dx*y;
        // Native radius applies AFTER the transpose, not to world-space body
        // cells. Those operations differ for coincident diagonal facing.
        for(int ox=-radius;ox<=radius;ox++)
        for(int oy=-radius;oy<=radius;oy++)
            if(localX+ox is >=int.MinValue and <=int.MaxValue
                &&localY+oy is >=int.MinValue and <=int.MaxValue
                &&points.Contains(((int)(localX+ox),(int)(localY+oy))))return true;
        return false;
    }

    internal IEnumerable<(int Dx,int Dy)> CardinalOffsets(int radius)
    {
        if(radius is <-128 or >127)yield break;
        radius=Math.Max(0,radius);
        // For a cardinal orthonormal transform, radius membership can be
        // inverted exactly in local coordinates before the forward transform.
        foreach(var p in Raw)
        for(int x=-radius;x<=radius;x++)
        for(int y=-radius;y<=radius;y++)
        {
            int dx=p.Dx-x,dy=p.Dy-y;
            yield return(dx,dy);yield return(-dy,dx);
            yield return(-dx,-dy);yield return(dy,-dx);
        }
    }
}
