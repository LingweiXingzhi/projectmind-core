"""Actual HTTP transport for D fixture acceptance, not the A product UI."""
from http.server import BaseHTTPRequestHandler
import json
from http.cookies import SimpleCookie
from urllib.parse import urlsplit, parse_qs

from extensions.continuity.fix_gateway import RequestContext
from extensions.handoff.architecture import ArchitectureError


def make_handler(service, gateway):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, payload):
            raw=json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

        def context(self):
            cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
            return RequestContext(self.client_address[0],self.headers.get('Host',''),
                self.headers.get('Origin',''),cookie['d-session'].value if 'd-session' in cookie else '',
                self.headers.get('X-CSRF-Token',''))

        def do_GET(self):
            query=parse_qs(urlsplit(self.path).query)
            try:
                if urlsplit(self.path).path == '/tasks':
                    value=service.get(query['id'][0]) if 'id' in query else service.listing()
                    return self.reply(200,{'result':value,'fixtureOnly':True})
                self.reply(404,{'code':'NOT_FOUND'})
            except ArchitectureError as exc:self.reply(exc.status,exc.as_dict())

        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 2_000_000:raise ArchitectureError('INVALID_INPUT','body limit',400)
                data=json.loads(self.rfile.read(size))
                if urlsplit(self.path).path == '/session':
                    result=gateway.create_session(data['actor'],self.context())
                elif urlsplit(self.path).path == '/actions':
                    result=gateway.call(data['action'],data['payload'],self.context())
                else:return self.reply(404,{'code':'NOT_FOUND'})
                self.reply(200,{'result':result,'fixtureOnly':True})
            except ArchitectureError as exc:self.reply(exc.status,exc.as_dict())
            except (TypeError,KeyError,ValueError) as exc:self.reply(400,{'code':'INVALID_INPUT','message':type(exc).__name__})
    return Handler
