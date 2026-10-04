"""Owned ring save/ACK/registry/reconnect/Redis batch, without user mutations."""
import json,struct,tempfile,unittest,uuid
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.build_journal import BuildJournal
from wakfu_server import builds,wire
from wakfu_server.inventory_items import grant
from wakfu_server.health import maximum
from wakfu_server.equipment_stats import bonuses,effective_character
from protocol_codec import Reader
from test_combat_group_redis import MemoryRedis

class RingBuildIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'world.sqlite3';self.now=[100.0]
        self.store=Store(self.path,clock=lambda:self.now[0])
        self.account=self.store.register('ring-test','private-local-test-password')['id']
        self.char=self.store.create_character(self.account,'Ring Test',breed=11)
        self.generation=self.store.begin_session(self.account,ttl=10000)
        self.store.select_character(self.account,self.generation,self.char['id'])
        with self.store.connection() as db:
            db.execute('UPDATE characters SET level=20,hp=80,max_hp=? WHERE id=?',(maximum(11,20),self.char['id']))
        self.char=self.store.character(self.account,self.char['id'])
        self.items=[grant(self.store,self.account,self.generation,self.char['id'],reference=2022,quantity=1,container=self.char['inventory_containers'][0]['uid'],slot=slot,allowed_references={2022}) for slot in (0,1)]
        self.client=MemoryRedis();self.namespace='wakfu:test:ring:'+uuid.uuid4().hex
        self.journal=BuildJournal(self.store,self.client,namespace=self.namespace,clock=lambda:self.now[0]);self.store.build_journal=self.journal

    def blobs(self,slot=7):
        return dict(sheet=b''.join(wire.proto_field(t,v) for t,v in [(8,0),(18,b'Own ring'),(24,(1<<64)-1),(56,1)]),equipment=wire.proto_field(10,wire.proto_field(8,self.items[0]['uid'])+wire.proto_field(16,slot)),deck=b'',aptitudes=b'')

    def save(self,blobs):
        request=struct.pack('>q',self.char['id'])+b''.join(struct.pack('>I',len(blobs[k]))+blobs[k] for k in builds.KEYS)
        character,index,decoded=builds.decode(request)
        return self.store.save_build(self.account,self.generation,character,index,decoded)

    def test_ring_ack_registry_reopening_and_redis_reconnect_keep_real_uid_once(self):
        blobs=self.blobs();saved=self.save(blobs)
        self.assertEqual(bonuses(saved)['stats'],{1:5,20:5})
        self.assertEqual((saved['hp'],saved['max_hp']),(80,maximum(11,20)+5))
        r=Reader(builds.response_messages(saved,0,wp=6)[0][1])
        self.assertEqual((r.number('q'),r.number('i'),r.number('b'),r.number('B')),(saved['id'],0,0,1))
        decoded={key:r.take(r.number('I')) for key in builds.KEYS};r.finish()
        self.assertEqual(decoded['equipment'],blobs['equipment'])
        original=wire.proto_field(10,wire.proto_field(16,wire.TEMPLATE_CHARACTER))
        packet=wire.attribute_sheets(struct.pack('>I',len(original))+original,[saved])
        registry=dict(wire.proto_fields(dict(wire.proto_fields(packet[4:]))[10]))
        self.assertEqual(registry[16],saved['id'])
        selected=dict(wire.proto_fields(registry[10]));self.assertEqual(selected[8],0)
        self.assertEqual(selected[18],blobs['equipment'])
        reopened=Store(self.path,clock=lambda:self.now[0])
        reopened.build_journal=BuildJournal(reopened,self.client,namespace=self.namespace,clock=lambda:self.now[0])
        loaded=reopened.character(self.account,saved['id'])
        self.assertEqual(loaded['builds'],saved['builds'])
        self.assertEqual(effective_character(loaded)['max_hp'],maximum(11,20)+5)
        repeated=self.save(blobs)
        self.assertEqual((repeated['hp'],repeated['max_hp']),(80,maximum(11,20)+5))
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM character_builds').fetchone()[0],0)
        self.now[0]+=1200;self.assertEqual(self.journal.flush_due(),1)
        with self.store.connection() as db:self.assertEqual(bytes(db.execute('SELECT equipment FROM character_builds').fetchone()[0]),blobs['equipment'])

    def test_move_between_ring_slots_and_reject_second_same_equipped_without_partial_save(self):
        self.save(self.blobs(7));moved=self.save(self.blobs(8))
        self.assertEqual(moved['builds'][0]['equipment'],self.blobs(8)['equipment'].hex())
        bad=dict(self.blobs(8),equipment=self.blobs(8)['equipment']+wire.proto_field(10,wire.proto_field(8,self.items[1]['uid'])+wire.proto_field(16,7)))
        with self.assertRaisesRegex(ValueError,'EQUIP criteria'):
            self.save(bad)
        self.assertEqual(self.store.character(self.account,self.char['id'])['builds'],moved['builds'])
