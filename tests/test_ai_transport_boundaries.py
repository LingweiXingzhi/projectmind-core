"""Real local HTTP boundary cases; synthetic key only, never real provider calls."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from archloop import ai_transport as transport


class TransportBoundaryTests(unittest.TestCase):
    def endpoint(self,handler):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}/v1'

    def env(self,base):return patch.dict(os.environ,{'PROJECTMIND_AI_API_KEY':'SYNTHETIC-NOT-A-REAL-KEY',
        'PROJECTMIND_AI_MODEL':'fixture-model','PROJECTMIND_AI_BASE_URL':base,'PROJECTMIND_AI_PROTOCOL':'chat_completions'})

    def test_redirect_never_contacts_the_destination(self):
        received=[]
        class Destination(BaseHTTPRequestHandler):
            def do_GET(self):received.append(self.headers.get('Authorization'));self.send_response(200);self.end_headers()
            do_POST=do_GET
            def log_message(self,*args):pass
        destination=self.endpoint(Destination)
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):self.send_response(302);self.send_header('Location',destination);self.end_headers()
            def log_message(self,*args):pass
        with self.env(self.endpoint(Redirect)):
            with self.assertRaises(transport.AIError) as error:transport.call_model('fixture',{},'s',{'type':'object'})
        self.assertIn('HTTP 302',str(error.exception));self.assertEqual(received,[])
        self.assertNotIn('SYNTHETIC',str(error.exception))

    def test_oversize_invalid_json_and_nonfinite_replies_are_controlled(self):
        class Reply(BaseHTTPRequestHandler):
            payload=b'not JSON';declared=None
            def do_POST(self):
                self.send_response(200);self.send_header('Content-Length',str(self.declared or len(self.payload)));self.end_headers()
                self.wfile.write(self.payload)
            def log_message(self,*args):pass
        base=self.endpoint(Reply)
        with self.env(base):
            for payload,declared in [(b'not JSON',None),(b'[]',None),(b'['*1100+b']'*1100,None),(b'',transport.MAX_RESPONSE_BYTES+1),
                (json.dumps({'choices':[{'message':{'content':'{"n": NaN}'}}]}).encode(),None)]:
                Reply.payload=payload;Reply.declared=declared
                with self.subTest(payload=payload[:30]):
                    with self.assertRaises(transport.AIError):transport.call_model('fixture',{},'s',
                        {'type':'object','properties':{'n':{'type':'number'}}})

    def test_remote_cleartext_and_bad_port_refused_before_contact(self):
        for base in ('http://provider.example.invalid/v1','https://example.invalid:bad/v1','https://:123/v1'):
            with self.env(base), patch.object(transport,'urlopen') as network:
                with self.assertRaises(transport.AIError):transport.call_model('fixture',{},'s',{'type':'object'})
                network.assert_not_called()

    def test_request_size_and_nonfinite_input_refused_before_contact(self):
        with self.env('http://127.0.0.1:1/v1'),patch.object(transport,'urlopen') as network:
            for payload in ({'body':'x'*(transport.MAX_REQUEST_BYTES+1)},{'n':float('nan')}):
                with self.assertRaises(transport.AIError):transport.call_model('fixture',payload,'s',{'type':'object'})
            network.assert_not_called()

    def test_public_status_and_schema_error_do_not_echo_private_values(self):
        with self.env('https://provider.example.invalid/private-SYNTHETIC-TOKEN/v1'):
            self.assertNotIn('SYNTHETIC',json.dumps(transport.ai_status()))
        with self.assertRaises(transport.AIError) as error:
            transport._validated({'SYNTHETIC-CREDENTIAL-FIELD':'x'},
                {'type':'object','additionalProperties':False,'properties':{}})
        self.assertNotIn('SYNTHETIC',str(error.exception))
