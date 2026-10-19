"""Native combat formation corridors stay reachable and terrain-authentic."""
import base64
import json
import unittest
import zlib

from wakfu_server.combat.combat_arena_interior import safe_interior
from wakfu_server.combat.combat_placement_cells import generate


# Sanitized geometry only: fight 333 has 231 walkable cells, directed native edges, perimeter,
# and the six participant coordinates needed to reproduce the formation check.
# SHA-256 of the canonical uncompressed JSON: 336dc1aac19f77fdead9fb8932283804b33929de623478598a14fd0116e75fed.
_FIGHT333 = """
c-qaK--;*44Taxjug6eQ{q4Mp*$a~lAz(vrd>8WWv8UI+uA@3fObh{Eif^T^nw^nOcdOL@{_@xNAAkJUm%n`f{daY|eP^S-&GPl_cgw-Dx3NB~4y@m7v-)~#n>E4eU^TGn?^c7gG`L=a>wQ?|ZTQQ2uJ>ULusT=`EVz2Rz<TYde)~ymR@tq7fi-u(XDt=hQeiC>*79LFSO!+vt!LF0R_*ssaBP-=Rd(ywJ@oZh5arpC!;Tzw<gg=$9XagCVMh)-a@di>j_lr1-z)>G?AC8Pvd5ZxlxGhHdob98!5$3uV6X>+Js9l4U=IcMP+$)Q_E7FUwDnkXkMiuHz#a<hp}-yr?4iIO3hbf49?HH4zxF-cmVs4v>$m@h&6<0Z*B)-GgH^#Yu*z<|)_Gg6buL)vf^{xf=lb@u-Ykgnta`z!7p!{0s@MLrzAXc*>{f%TKYN(4vI#4ju(Am&o3OG8E1R&g2`ihhvI#4ju(AOw8?dqgD;uz~0V^BdR_2f8zznRiTMe%MtgPSvx105>6Ka)1t-7rNRtKws<zN|DaP<aPf7aPxWervaRn4KQIaD==I(AzQmVs4vtHITul~q_-g_S{#bEt6+HO`^NIn+3Z8s|{s9BQ0HjdQ4R{;jI*R@tp*4^Y({s+vPpbEs+#Rn4KQIaD==I_6Nv9O{@Gtju6#P^%njl|!v^s8tTN%Ar;{)GCKs<xr~}YLypQ8B`#L3gl3M94e4Q1#+lB4i(6u0y$J5hYDoZ{y%Nk{`0&o_?NF$8`K<wnsZwXth!sz)fZeHYKKAXFsK~{wZoux+*Sjt?$&el30H^uU{D_n>VrXjFsKi=)xfH|^;~_x)u9F$)BuATU{C`LYQSwZus*K-_3g|1-~Rsoaj%lxto&;7o0po>k6Rl?JB$3f5gI9dZj5f)&+EFPxo=~>rgn7RplRPmuFG!cHj1}*OVP%B$;}|6Pm$YbJ8vr`t%^2w-I}hdo;Qs*RX430mA_Zy7PqF<0yXuULvEK{(dXuNqpzFm=Vtez;eUVPPlMfxGg_JNP`^3qww}?-uG`gb4tYc{QrZ-)EOJx7SL9(tPia-OvdC5aEu4=%v~MN8>>&xGk8IoMIv=+%T0>-f02BWf)Z-aOJ^Z%g!<^@LpV6B7J`aKzb+RgaY^3S)cxIzA$ErtAj5_lj>TiKO&YCIhiaLudGe3E7Hd5LYbrxCH1@eflr?e{SEV8UA<Y8b-sVnL%vZre%j~y9xc3n$XMIK=?>g>8DT~$#zryh?M<8?zeyA-XdFUwcqA!dxcR2HpgCX~J&eAOf0jhf14<N>j#v?%&KnB8bmx$b-veXOdeOo$JzV+KASYsc%d$J`s0T7^6mUnw1m8jCEI40-%MQ`!|Z7FjA8@}PgDv?*#VvQ#qUl|oNxRn%BysdLE7i<VMX)L3L!d6K*)sVOx@jYT$<Mac^pPiaxqSmdIz==thL`^GHl$19f@S!>brC6o4LIX1l9iIJs_^)q`*UkkqK<rkyROQwy!UNglUOJ1Z&-{&<OqlK-iq-!Rx>=-TNy7+?cpi<?k*MW={<|}n9d9^rG+7&G<vedEUCFV$JQ?#(iQpb|lr9Gup(ZV829ZO!!wv@V}g+-Psm%IY5DK$k4i!3!TdD-kKEs7QvSt{i7wYK(+nb3~c$uY84$ma`m?aT6HcyS#gOZ{wT29~}h_?9z2Z&_5m_9t|Ey}nUXS(LO8cuI?)+l%~-7M1zWW(Dp0v@#I7wG2EI8y_Uy8Voin)wOD(AarY1*r?Rcq#<Lbv<temMQl{+XVUsHQrZOF8Zb60^)qQQ=_##&N`*`sR$5A3(5;DNqf#N0)|i@73sh=g(q`i+ErM>1FdLN`_-yFWzA;ahqsb;l)*AS19n!umi-vZd7+EUha^`2{yEO`ZP;6<6SyVPWF}j$qQpl`%%2QetT`aQF&!kOD`o<g^=pvC{EnhM7lZLRvS7~qAKE~)`zDixQR<xPYuIOTsmAYn4Z_0OTHQT7tv7v!(F{(77Y`0@{F<+(nNb8>Tjeq-rE)rR)KGGy8eQ9P0&3Q4h(uAQM@ydL+w!fRMOcTo1#*Hdn#~L9$r6o|M+(=X9ab41K`A}@ZjFDM`CZm%@#&*t}PDLlXu2PJwadf40C^}hWr5IU@>P%@@bh5}wF|uY@={uRPQf{)bmeI+4U1dVmq|4}J*Hzk#HT-%?i=vZ7R@#iT7Hi*_&DPQU8zW0?Mw*zlFUxhI%{WGu%59xlRQk@~JI}0gDH{Lw=h^-oeV6*%CvDtUN~fZOMV2avG>os54n+rxEL9L`O`j?4iVhZ8Y9!JGFMS8|l?qBV)HC|DxNp=|W+2V^HKnHLV3DPABgX(drA5)fB1`3V9yrjxF*D5LNI;CNmD_o=LHn}25e^^3$WqtMGb2gg5qw9gbJT$hMmzJBI)@zYxKcV5?JTm?Ipi40O6gFvv&d5CkOM0-rCrg^B1;uSj>bse&U{}7X=2_`$7~qw%vY))a%5-Ab?QJ5qn$;TDu^5o@{|@uJBut;(0L3=`^L;Lj-x>_vQ|OofhX<D@<up>6eCNGG|r49eS7d#2eBTi71VibYm|)krD$W3rGg>{#IBT1MH`DO6%;v&wo*D2Z7i}>P~_0tOleoNvB*+ik>hpJw=rL-uhdaJMnmsqIM_Fsub)Q(B{fAGi!2osIbi51Es8c4St_XWD5Lg`S*0I`4P#`jpw2^++Lz^=aI7&#minrn*-ZL|zRhr$Gv*C-)RWQ5e5HaS$40M|PDLw=EEN<vpt@2z6s;_>R8Zt7>`ZA_w6e%jUy(z%(zi0-s`7?9z{_Z5zEVMv!@xDArf6l6rGg^Ijy<JC(aIuA1$7>9*1j<_wByimjI0&Zd6ZiFvb+(FH^<0QU$rwMN#D?m7>;<yyrB+&GwRG&svvTh{7UIm)LCSyg2=J;mC~W8v&d2fkpuEGrCm{Hk)=i=NAX8Wo1)Glw{*=-<*Rxgr;pc_+KdbkXeo6?okf<~jEpL%DK$l%MV8u(3`OvimO!QYItMHq*DWd|)nm*-jI7nyIm$u%vV0W=D#XZAo7FQDO5e~EC`U|ew4CE86y0;3r>gH9UlFg%hFdUdEV5L6WKhPH(y6Gi$Wrx@ksK?fLs4UqrRpQYKW0k1qQ)XiO-RO!jFdJ-jYV!MPm+NqJ*8DqW09p&C8JYXN?lQ7k)={4Lt3P-F<+?()xZ}<jreNScMgxyzARsbfi5w!)P#O!Lg^d2@4`@<m^akOn~h3cM+W3vDV>TI7Fp^#GKy!VbSPR_WU1@O(4U#ou4rMArLH66g+@x7qJ>44s*emZ>M5;?78Y5mJ~A??rPLKIEV5L6WH?hzsVQ1mWJ}j<DkIrBiYZ=Ks=jlil=h7o$&R5<F|t;D=kO}+%kotiFBKz8O=xE(l)kYiu%sGEjoc!18+5f%se;J(u9eaus9h|wR6%4=*i2~`)GiiTsvt6wY^1aaY8Q(vRS+3|)>B#q-3F3vRH`5{X04^v1+|MsmKuo+bgL<~KuzThG91oRS^|~o>l`$9T(_vqP*Qz$4y}vVWh3o2D)m)4v&to?g&sLME|1ZLcba6lUQYW`bdl>yZN|p<T`8T4E*4p7Gd3`ArF1B|SY)Nm*l5C;(yr)Yk(D-MLl8$wo1%+FR@#h>TkI*ViY^veX)`j|QTo~<zOu5DA(1;>$KT-occey2GCGNG_#3<wU8!&UOIhb|$rxFw5jF_(O6gQ|vdBt}u#uZ9r9;ulA}ck*hI`JGc10(Ptkeh_BRW#r6rC)xQX_0&X-{cYbh5}wjgZl(+IJFPT_w*kt2>=(l~hAn86Ct|SIKk0tM-k5Df1l98Y9apNk++DDV>TA7FkwFGPHK3bSOGlWLYK2c-)!NuIONqWtAj@ct=W`qJu@2Rg#SS?J2E_4i;I~&~v!3_8r7mSJ;tONj13mp}NwYV~%5FHUxR2vX+sN$yZ8ept4$#@yjcvBT!k7$SCKT(jKU+IAkpJNNEdH))X>gx~H@TDr?F(e`D|KetrA$&-b7I@zeV+??210?fjX(uk-mY>iog4=A_@r`TX~8k}ur!_1Q1SWM7BLzSfd{k)`SHtYlwLNxzWt>2IR^;qRWTKlU|~^cy9~mq*esh$P<yNx$!re5WJ*-bV5jjr406O@F!KfA~5@_U(x5YZ3P8?=}4YzqIiAZzO#Fdj@}wZx8(P{=-l9k-4#{7-cmM0rzu2&9}#N|M@T6AUiw"""


def _fight333():
    return json.loads(zlib.decompress(base64.b85decode(_FIGHT333.strip())))


class CohesiveFormationTests(unittest.TestCase):
    @staticmethod
    def _reachable(edges, start, blocked=()):
        outgoing = {}
        for source, target in edges:
            outgoing.setdefault(tuple(source), set()).add(tuple(target))
        blocked = set(map(tuple, blocked))
        found = {tuple(start)}
        pending = [tuple(start)]
        while pending:
            for target in outgoing.get(pending.pop(), ()):
                if target not in blocked and target not in found:
                    found.add(target)
                    pending.append(target)
        return found

    def test_fight333_native_geometry_keeps_all_six_formation_seeds_safe(self):
        native = _fight333()
        cells = {tuple(cell) for cell in native["cells"]}
        edges = [(tuple(a), tuple(b)) for a, b in native["edges"]]
        seeds = {
            0: {(-28, -156, 40)},
            1: {tuple(position) for position in native["team1"]},
        }
        perimeter = {tuple(cell) for cell in native["perimeter"]}

        interior, borders = safe_interior(cells, edges, seeds, perimeter)
        placements = generate(
            interior,
            [(a, b) for a, b in edges if a in interior and b in interior],
            seeds,
            slots_per_team=12,
            spread_teams=True,
            variation_seed=333,
        )

        required = seeds[0] | seeds[1]
        self.assertEqual(len(cells), 231)
        self.assertEqual(len(edges), 774)
        self.assertTrue(required <= interior)
        self.assertFalse(required & borders)
        self.assertTrue(borders <= perimeter)
        forward = self._reachable(edges, min(seeds[0]), borders)
        reverse_edges = [(target, source) for source, target in edges]
        reverse = self._reachable(reverse_edges, min(seeds[0]), borders)
        self.assertTrue(required <= forward)
        self.assertTrue(required <= reverse)
        self.assertEqual(placements[0] & placements[1], set())
        self.assertTrue(placements[0] <= interior)
        self.assertTrue(placements[1] <= interior)
        self.assertEqual(len(placements[0]), 12)
        self.assertEqual(len(placements[1]), 12)
        self.assertTrue(all(cell[2] == 40 for cell in placements[0]))
        self.assertTrue(required <= placements[0] | placements[1])
        placed = placements[0] | placements[1]
        self.assertTrue(placed <= cells)
        self.assertTrue(placed <= forward)
        self.assertTrue(placed <= reverse)

    def test_folded_native_paths_prefer_longer_hazard_free_corridor(self):
        cells = {
            (0, 0, 0),
            (1, 0, 0),
            (2, 0, 0),
            (0, 1, 0),
            (1, 1, 0),
            (2, 1, 0),
        }
        edges = []
        for a, b in [
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (2, 0, 0)),
            ((0, 0, 0), (0, 1, 0)),
            ((0, 1, 0), (1, 1, 0)),
            ((1, 1, 0), (2, 1, 0)),
            ((2, 1, 0), (2, 0, 0)),
        ]:
            edges.extend(((a, b), (b, a)))
        seeds = {0: {(0, 0, 0)}, 1: {(2, 0, 0)}}

        interior, borders = safe_interior(cells, edges, seeds, {(1, 0, 0)})

        self.assertIn((1, 0, 0), borders)
        self.assertNotIn((1, 1, 0), borders)
        self.assertTrue(seeds[0] | seeds[1] <= interior)
        self.assertTrue(interior <= cells)

    def test_folded_xy_neighbor_does_not_pull_formation_remote_leaf(self):
        # This native path folds around a rectangle. Its final leaf is only one
        # XY unit from the origin but remains seventeen directed steps away.
        path = [
            (0, 0, 0),
            (0, 1, 0),
            (0, 2, 0),
            (0, 3, 0),
            (0, 4, 0),
            (1, 4, 0),
            (2, 4, 0),
            (3, 4, 0),
            (4, 4, 0),
            (5, 4, 0),
            (5, 3, 0),
            (5, 2, 0),
            (5, 1, 0),
            (5, 0, 0),
            (4, 0, 0),
            (3, 0, 0),
            (2, 0, 0),
            (1, 0, 0),
        ]
        enemy = (0, -1, 0)
        cells = set(path) | {enemy}
        edges = []
        for source, target in zip(path, path[1:]):
            edges.extend(((source, target), (target, source)))
        edges.extend(((path[0], enemy), (enemy, path[0])))
        seeds = {0: {path[0]}, 1: {enemy}}

        placements = generate(
            cells,
            edges,
            seeds,
            slots_per_team=3,
            spread_teams=True,
        )
        distances = self._reachable(edges, path[0])
        # The remote leaf is an apparent XY neighbor; native distance wins.
        self.assertEqual(
            abs(path[-1][0] - path[0][0]) + abs(path[-1][1] - path[0][1]), 1
        )
        self.assertEqual(self._distance_on_edges(edges, path[0], path[-1]), 17)
        self.assertEqual(len(placements[0]), 3)
        self.assertLessEqual(
            max(
                self._distance_on_edges(edges, path[0], cell) for cell in placements[0]
            ),
            2,
        )
        self.assertNotIn(path[-1], placements[0])
        self.assertTrue(placements[0] <= distances)

    @staticmethod
    def _distance_on_edges(edges, start, target):
        outgoing = {}
        for source, destination in edges:
            outgoing.setdefault(source, set()).add(destination)
        distances = {start: 0}
        pending = [start]
        while pending:
            current = pending.pop(0)
            if current == target:
                return distances[current]
            for neighbor in outgoing.get(current, ()):
                if neighbor not in distances:
                    distances[neighbor] = distances[current] + 1
                    pending.append(neighbor)
        raise AssertionError("Placement cell is not natively reachable")

    def test_height_ramp_corridor_preserves_native_levels_and_edges(self):
        cells = {(0, 0, 0), (1, 0, 5), (2, 0, 10)}
        edges = [
            ((0, 0, 0), (1, 0, 5)),
            ((1, 0, 5), (0, 0, 0)),
            ((1, 0, 5), (2, 0, 10)),
            ((2, 0, 10), (1, 0, 5)),
        ]
        seeds = {0: {(0, 0, 0)}, 1: {(2, 0, 10)}}

        interior, borders = safe_interior(cells, edges, seeds, {(1, 0, 5)})
        placements = generate(
            interior, edges, seeds, slots_per_team=1, spread_teams=True
        )

        self.assertEqual(interior, cells)
        self.assertEqual(borders, frozenset())
        self.assertEqual(placements, seeds)
        self.assertTrue(all(a in interior and b in interior for a, b in edges))
        self.assertTrue(placements[0] | placements[1] <= cells)
        self.assertEqual({cell[2] for cell in interior}, {0, 5, 10})

    def test_required_narrow_corridor_cell_is_reserved_from_border(self):
        cells = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}
        edges = []
        ordered = sorted(cells)
        for a, b in zip(ordered, ordered[1:]):
            edges.extend(((a, b), (b, a)))
        seeds = {0: {(0, 0, 0)}, 1: {(2, 0, 0)}}

        interior, borders = safe_interior(cells, edges, seeds, {(1, 0, 0)})

        self.assertEqual(interior, cells)
        self.assertEqual(borders, frozenset())

    def test_disconnected_native_seed_groups_are_rejected(self):
        cells = {(0, 0, 0), (1, 0, 0), (4, 0, 0), (5, 0, 0)}
        edges = [
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (0, 0, 0)),
            ((4, 0, 0), (5, 0, 0)),
            ((5, 0, 0), (4, 0, 0)),
        ]

        with self.assertRaisesRegex(ValueError, "no mutual native interior corridor"):
            safe_interior(
                cells,
                edges,
                {0: {(0, 0, 0)}, 1: {(5, 0, 0)}},
                set(),
            )


if __name__ == "__main__":
    unittest.main()
