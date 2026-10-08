"""Real HTTP download transport with controlled handover payloads, not B approval."""
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
import app
from tests.test_archloop_a_service import service_with_git


class HandoverDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.service=service_with_git(Path(cls.temp.name))
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),app.make_handler(app.ROOT,app.MAP_PATH,archloop_service=cls.service))
        cls.port=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()

    def request(self, packet, query=None, origin=None):
        url='/api/archloop/workspaces/ws_download/handover'+('?' + urlencode(query) if query else '')
        with patch.object(self.service,'export_handover',return_value=packet):
            connection=HTTPConnection('127.0.0.1',self.port,timeout=10)
            connection.request('GET',url,headers={'Origin':origin} if origin else {})
            result=connection.getresponse();body=result.read();headers=dict(result.getheaders());status=result.status;connection.close()
        return status,headers,json.loads(body)

    def packet(self):
        return {'mapRevision':'sha256:'+'a'*64,'mapSourceRevision':'b'*40,'note':'测试交接'}

    def test_normal_get_keeps_json_contract(self):
        packet=self.packet();status,headers,body=self.request(packet)
        self.assertEqual(status,200);self.assertEqual(body,packet)
        self.assertNotIn('Content-Disposition',headers)

    def test_download_is_attachment_and_binds_visible_version(self):
        packet=self.packet();status,headers,body=self.request(packet,{'download':'1',**{k:packet[k] for k in ('mapRevision','mapSourceRevision')}})
        self.assertEqual(status,200);self.assertEqual(body,packet)
        self.assertEqual(headers['Content-Disposition'],'attachment; filename="handover-aaaaaaaaaaaa.json"')
        self.assertEqual(headers['Cache-Control'],'no-store')

    def test_public_packet_shape_uses_immutable_envelope(self):
        old=self.packet();packet={'versionEnvelope':{'version':{'mapRevision':old['mapRevision']},'provenance':{'mapSourceRevision':old['mapSourceRevision']}}}
        status,headers,body=self.request(packet,{'download':'1','mapRevision':old['mapRevision'],'mapSourceRevision':old['mapSourceRevision']})
        self.assertEqual(status,200);self.assertEqual(body,packet)
        self.assertIn('attachment',headers['Content-Disposition'])

    def test_old_preview_cannot_download_new_version(self):
        for query in ({'download':'1'},{'download':'1','mapRevision':'sha256:'+'c'*64,'mapSourceRevision':'b'*40},{'download':'1','mapRevision':'sha256:'+'a'*64,'mapSourceRevision':'c'*40}):
            with self.subTest(query=query):
                status,headers,body=self.request(self.packet(),query)
                self.assertEqual(status,409);self.assertEqual(body['error']['code'],'REVISION_CONFLICT')
                self.assertNotIn('Content-Disposition',headers)

    def test_download_keeps_same_origin_guard(self):
        packet=self.packet();status,_,body=self.request(packet,{'download':'1',**{k:packet[k] for k in ('mapRevision','mapSourceRevision')}},'https://elsewhere.invalid')
        self.assertEqual(status,403);self.assertEqual(body['error']['code'],'FORBIDDEN_ORIGIN')
