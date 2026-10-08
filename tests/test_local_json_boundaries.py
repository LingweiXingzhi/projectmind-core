"""Raw local HTTP malformed JSON must fail before any workspace mutation."""
import http.client
import json
import unittest

import test_archloop_a_backend_b as fixtures
from archloop_http_session import establish_session, CSRF_HEADER


class LocalJsonBoundaryTests(unittest.TestCase):
    def test_nonfinite_and_deep_input_rejected_without_mutation(self):
        runtime = fixtures.HttpSeamTests
        runtime.setUpClass()
        try:
            origin = f"http://127.0.0.1:{runtime.port}"
            cookie, csrf = establish_session(origin, operator="Fixture JSON boundary")
            client = runtime()
            before = client.call("GET", "/api/archloop/workspaces")
            prefix = b'{"context":"planning","title":"Fixture boundary","goals":"fixture","constraints":"fixture","extra":'
            cases = [prefix + atom + b'}' for atom in (b'NaN', b'Infinity', b'-Infinity', b'1e9999')]
            cases += [prefix + b'[' * depth + b'0' + b']' * depth + b'}' for depth in (65, 1600)]
            for raw in cases:
                with self.subTest(size=len(raw)):
                    connection = http.client.HTTPConnection("127.0.0.1", runtime.port, timeout=5)
                    try:
                        connection.request("POST", "/api/archloop/workspaces", body=raw, headers={
                            "Content-Type": "application/json", "Origin": origin,
                            "Cookie": cookie, CSRF_HEADER: csrf})
                        response = connection.getresponse()
                        payload = json.loads(response.read())
                        self.assertEqual(response.status, 400, payload)
                    finally:
                        connection.close()
            self.assertEqual(client.call("GET", "/api/archloop/workspaces"), before)
            status, _ = client.call("POST", "/api/archloop/workspaces", {
                "context": "planning", "title": "Valid fixture", "goals": "fixture", "constraints": "fixture"})
            self.assertEqual(status, 200)
        finally:
            runtime.tearDownClass()


if __name__ == "__main__":
    unittest.main()
