"""Explicit durable lifecycle fixtures for World authority tests.

These helpers install supplied due-cycle state. They do not observe clocks,
choose transitions, compute randomness, or run a retired Python planner.
The fixed 32-event block was qualified against native Rust seed 17*32 output.
"""

from copy import deepcopy
import json
from psycopg.types.json import Jsonb

FROZEN_DECISIONS = json.loads(r"""[
{"cycle":1,"draw":0.010467071100477399,"group_draw":0.7258884206631919,"destination_draw":0.762735189984985,"variant_seed":"0e04e1e2b252af726f6a8cc8d07173e481c9a19afa2ec0e2181377818467baff","attempts":0},
{"cycle":2,"draw":0.6847553813097158,"group_draw":0.5656484624534008,"destination_draw":0.6475118353848149,"variant_seed":"5d2415d37a578f6b28adf28f076a48076fc925dad6a7cf7a5bf42a017c666615","attempts":0},
{"cycle":3,"draw":0.3203400275008157,"group_draw":0.6398962823931253,"destination_draw":0.9631859486843126,"variant_seed":"bfe7b126ecd0486af7dec0188c761f9bb949f2bfab2339978381b66fa3382e86","attempts":0},
{"cycle":4,"draw":0.9072719670730413,"group_draw":0.17985355691363525,"destination_draw":0.2451181761749377,"variant_seed":"48b8ce88fa2ce064f473078ab3edd9b10c6e724f858ab5d2748a07c1834f36d6","attempts":0},
{"cycle":5,"draw":0.31959699709288636,"group_draw":0.7622990648274143,"destination_draw":0.19129452112524492,"variant_seed":"5b1432fb807e026423ce0d12cb8ce629121796d74d7823ea34d171da638a3b01","attempts":0},
{"cycle":6,"draw":0.4195337985557619,"group_draw":0.9498707704806016,"destination_draw":0.7122818845153838,"variant_seed":"cc8e4e76b67ce8b220948ecb38ccf5c4d9bc7e609867f5e097e2cee1de68a7c3","attempts":0},
{"cycle":7,"draw":0.3148918575505596,"group_draw":0.3806358510265414,"destination_draw":0.04290601295842089,"variant_seed":"e2e962d7a2fa887c9b2b5466b4ff9242a6d955ad3df39d25fbddf3cb308c747d","attempts":0},
{"cycle":8,"draw":0.543987023442103,"group_draw":0.7575834004306675,"destination_draw":0.9935559931146621,"variant_seed":"be2e94993be4cc535e42f6d9be9d57c5d5422140b4177b334e4310ce1183cc07","attempts":0},
{"cycle":9,"draw":0.713739942097536,"group_draw":0.26562868518438787,"destination_draw":0.437802682117464,"variant_seed":"015bc6c2eccb6384e45d25703e79b2d259e437a1081e6fe583f5ef718155c627","attempts":0},
{"cycle":10,"draw":0.29955372999497987,"group_draw":0.024992743449734456,"destination_draw":0.530953261471101,"variant_seed":"ceeb8af576341687df32055b0568e0ce2e85f2e7e20e49340ee678deeb9c2fd2","attempts":0},
{"cycle":11,"draw":0.19412001091706466,"group_draw":0.10438300811338264,"destination_draw":0.7340899853510027,"variant_seed":"df1316c5fd753f59e8a3db591b5289bdc9749b5a25ebfc0b30fb649a28861d20","attempts":0},
{"cycle":12,"draw":0.3776550293070209,"group_draw":0.22030966239989203,"destination_draw":0.9809835810803232,"variant_seed":"b2ae652cb9a44acfb58042404aaa4e73453b276d98fa686dc4bef86fb984f100","attempts":0},
{"cycle":13,"draw":0.8989630671719642,"group_draw":0.07377650218825449,"destination_draw":0.8874206181825197,"variant_seed":"dc170c48b8e447480ca57846e6825a6f10c9ffc5cf6c78372d4561116597743a","attempts":0},
{"cycle":14,"draw":0.9167972683515894,"group_draw":0.36028145074141116,"destination_draw":0.6771667211133581,"variant_seed":"b97ded836afd55d106dbafb2753fde8c82061c1cbb4d8001a711378e20b5e20f","attempts":0},
{"cycle":15,"draw":0.04274318051990189,"group_draw":0.3612334976674496,"destination_draw":0.7286709622537016,"variant_seed":"67c1d907fc221926066abcb32b9e6acf3e5948860564db64aa089a6748970a6a","attempts":0},
{"cycle":16,"draw":0.49915855977955215,"group_draw":0.8731763803808049,"destination_draw":0.9270928784837218,"variant_seed":"f95939f36438d90a93b9e57db5601e8ec4393116f02a09f502f24eeebe984a08","attempts":0},
{"cycle":17,"draw":0.45658968347656725,"group_draw":0.5635565749406757,"destination_draw":0.8040532756003612,"variant_seed":"28d43531b6c9d3e927536ed951bbf47401f872b319eca19455cea548b5ae458a","attempts":0},
{"cycle":18,"draw":0.5588113724107296,"group_draw":0.4893603735359924,"destination_draw":0.36022634343849025,"variant_seed":"c1e1dbd82d29f760741dc36fe7debcba7fefc30bfec2b4af2e25e449eb31b811","attempts":0},
{"cycle":19,"draw":0.023146020845023818,"group_draw":0.23099764369374465,"destination_draw":0.84362421895287,"variant_seed":"b21f9401228f55d978fa462ac379030592ca506a0a462ae0cafac7b3003d06b8","attempts":0},
{"cycle":20,"draw":0.20250190508334542,"group_draw":0.46498424498930246,"destination_draw":0.6670509577484701,"variant_seed":"57bcbf8b18428277ba99a0183d19cd1aba491ed65deb37a83d8edbf0fcc9a230","attempts":0},
{"cycle":21,"draw":0.3136034452671618,"group_draw":0.05716673561452568,"destination_draw":0.44922114567906557,"variant_seed":"87808f59440657301bec0f35870e1b600ca658fe7939c7b1801197b41ab5dcab","attempts":0},
{"cycle":22,"draw":0.27123589813845583,"group_draw":0.1701155521677884,"destination_draw":0.7764011596950586,"variant_seed":"a14a03e4381708c5d5805b84a646a0b180791316d318016f14be73683ad572ef","attempts":0},
{"cycle":23,"draw":0.8715884879969971,"group_draw":0.25475200157820166,"destination_draw":0.35418252712833564,"variant_seed":"e5a9051ed1f3c1748f5bf492657ce683b3e949072ce9545b3d282535520656c8","attempts":0},
{"cycle":24,"draw":0.7699634645034777,"group_draw":0.41335939827157075,"destination_draw":0.05682539769043671,"variant_seed":"595c9d7305213b16e488573be5014fd0b96492e55541324fbc0c908127260e1d","attempts":0},
{"cycle":25,"draw":0.9764156211350057,"group_draw":0.7777327612968995,"destination_draw":0.09525922823300326,"variant_seed":"8286ba3511ca2d2caaa1918a9bed4a0f43e09e230628888460553420efcf58de","attempts":0},
{"cycle":26,"draw":0.6293737745483249,"group_draw":0.41974468709979196,"destination_draw":0.47378264424105654,"variant_seed":"23054566d448fff1c048127ae95a2259a4a20405a5bc10ddf29b0d16eb8fb6b9","attempts":0},
{"cycle":27,"draw":0.8837109456608735,"group_draw":0.8354900894487868,"destination_draw":0.7840661193021787,"variant_seed":"999787b87f4a405e07545c6a81c57bfc281be22b408ce87fe339589d7a1fa3f1","attempts":0},
{"cycle":28,"draw":0.5658820369530211,"group_draw":0.10819320845167135,"destination_draw":0.6100752053229471,"variant_seed":"737e4b4e306eaba743f49305a80b56b76aa79babc6c7fd3d5e97bea6ab442bd6","attempts":0},
{"cycle":29,"draw":0.6866499188443084,"group_draw":0.7846037084921942,"destination_draw":0.0852404601036193,"variant_seed":"0ea42e25231b45a780f8d540af248186c284792f73163040e856fc8737d8a58f","attempts":0},
{"cycle":30,"draw":0.023765862273021354,"group_draw":0.5879410429422223,"destination_draw":0.007918374584599985,"variant_seed":"48f8d0a2f685b0d91d05b96b9cfb72c9881c496cd8a57e0f4acc7638cce852b3","attempts":0},
{"cycle":31,"draw":0.4700566759963827,"group_draw":0.03721173795841848,"destination_draw":0.2557212160307817,"variant_seed":"5f7b1a5715647f3b9a02eb8b4bf73c04902cd1ab2acfd3464bfb7c7bf77437f5","attempts":0},
{"cycle":32,"draw":0.36504024690582937,"group_draw":0.4164717456286823,"destination_draw":0.5434907260775089,"variant_seed":"4fba09760bb14f066ca24a019de2f22a6aaf4c35231ac7e5fd16a230208dc0f3","attempts":0}
]""")


def _table(kind):
    if kind not in ("maturation", "reproduction"):
        raise ValueError("Unknown lifecycle fixture kind")
    return "monster_" + kind + "_timers"


def due_tickets(
    store,
    kind,
    map_id,
    instance_id,
    group_id,
    *,
    cycle=1,
    remaining_ms=0,
    member_ids=None,
):
    """Install an explicit due-cycle fixture for this registered source roster."""
    table = _table(kind)
    with store.connection() as db:
        row = db.execute(
            "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s "
            "AND group_id=%s",
            (map_id, instance_id, group_id),
        ).fetchone()
        if row is None:
            raise AssertionError("Missing registered lifecycle fixture group")
        tickets = []
        for member in row["members"]:
            if member_ids is not None and member["id"] not in member_ids:
                continue
            db.execute(
                f"INSERT INTO {table}(map_id,instance_id,monster_id,reference,"
                "remaining_ms,last_active_ms,observer_generation,due,cycle) "
                "VALUES(%s,%s,%s,%s,%s,NULL,NULL,true,%s) "
                "ON CONFLICT(map_id,instance_id,monster_id) DO UPDATE SET "
                "reference=EXCLUDED.reference,remaining_ms=EXCLUDED.remaining_ms,"
                "last_active_ms=NULL,observer_generation=NULL,due=true,cycle=EXCLUDED.cycle",
                (map_id, instance_id, member["id"], member["ref"], remaining_ms, cycle),
            )
            tickets.append(
                dict(
                    map_id=map_id,
                    instance_id=instance_id,
                    group_id=group_id,
                    monster_id=member["id"],
                    reference=member["ref"],
                    cycle=cycle,
                )
            )
    return tickets


def pending_tickets(store, kind, map_id, instance_id):
    """Read the explicit frozen fixture after reopen; no time or policy work."""
    table = _table(kind)
    with store.connection() as db:
        return [
            dict(row)
            for row in db.execute(
                f"SELECT t.map_id,t.instance_id,t.monster_id,t.reference,t.cycle,m.group_id "
                f"FROM {table} t JOIN combat_group_members m USING(map_id,instance_id,monster_id) "
                "JOIN combat_groups g USING(map_id,instance_id,group_id) "
                "WHERE t.map_id=%s AND t.instance_id=%s AND t.due AND g.status!='defeated' "
                "ORDER BY t.monster_id",
                (map_id, instance_id),
            )
        ]


def read_decision_fixture(store, kind, ticket):
    _table(kind)
    with store.connection() as db:
        row = db.execute(
            "SELECT incarnation,policy,events->(%s-block_start)::integer AS decision "
            "FROM monster_life_plans WHERE map_id=%s AND instance_id=%s "
            "AND monster_id=%s AND kind=%s",
            (
                ticket["cycle"],
                ticket["map_id"],
                ticket["instance_id"],
                ticket["monster_id"],
                kind,
            ),
        ).fetchone()
    if row is None:
        return None
    return dict(
        ticket,
        plan_incarnation=row["incarnation"],
        plan_policy=row["policy"],
        decision=row["decision"],
    )


def attach_decision_fixture(
    store, kind, ticket, configuration, *, incarnation="17" * 16
):
    """Seed one literal Rust-qualified decision block for World fencing tests."""
    _table(kind)
    if not 1 <= ticket["cycle"] <= 32:
        raise AssertionError("This literal fixture covers cycles 1..32 only")
    with store.connection() as db:
        db.execute(
            "INSERT INTO monster_life_plans(map_id,instance_id,monster_id,kind,reference,"
            "seed,incarnation,policy,version,block_start,events) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,1,1,%s) ON CONFLICT DO NOTHING",
            (
                ticket["map_id"],
                ticket["instance_id"],
                ticket["monster_id"],
                kind,
                ticket["reference"],
                "17" * 32,
                incarnation,
                Jsonb(configuration),
                Jsonb(deepcopy(FROZEN_DECISIONS)),
            ),
        )
    return read_decision_fixture(store, kind, ticket)
