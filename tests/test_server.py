"""Exercise the demo's HTTP boundary with synthetic requests and no inference."""
import http.client
import tempfile
from pathlib import Path
from unittest.mock import patch
import threading
import unittest

from server import make_server


class ServerOriginTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        app = Path(temporary.name)
        (app / "index.html").write_text("<html>Synthetic lab</html>")
        fixture = patch("server.APP", app)
        fixture.start()
        self.addCleanup(fixture.stop)

    def start_server(self, origin=None):
        httpd = make_server(0, origin)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(httpd.shutdown)
        return httpd

    def request(self, httpd, host=None, origin=None):
        headers = {}
        if host is not None:
            headers['Host'] = host
        if origin is not None:
            headers['Origin'] = origin
        connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=2)
        try:
            connection.request('GET', '/', headers=headers)
            response = connection.getresponse()
            response.read()
            return response.status
        finally:
            connection.close()

    def test_direct_loopback_remains_available(self):
        httpd = self.start_server()
        self.assertEqual(httpd.server_address[0], '127.0.0.1')
        self.assertEqual(self.request(httpd), 200)
        authority = f'localhost:{httpd.server_port}'
        self.assertEqual(self.request(httpd, authority, 'http://' + authority), 200)
        self.assertEqual(self.request(httpd, 'oral-board-local-lab.localhost'), 403)

    def test_only_the_configured_proxy_origin_is_accepted(self):
        origin = 'https://oral-board-local-lab.localhost'
        httpd = self.start_server(origin)
        self.assertEqual(self.request(httpd, 'oral-board-local-lab.localhost', origin), 200)
        self.assertEqual(self.request(httpd, 'oral-board-local-lab.localhost'), 200)
        for host, other_origin in [
            ('other.localhost', origin),
            ('oral-board-local-lab.localhost.evil.example', origin),
            ('oral-board-local-lab.localhost', 'https://evil.example'),
            ('oral-board-local-lab.localhost', 'http://oral-board-local-lab.localhost'),
        ]:
            with self.subTest(host=host, origin=other_origin):
                self.assertEqual(self.request(httpd, host, other_origin), 403)

    def test_worktree_and_custom_port_match_exactly(self):
        origin = 'http://fix-ui.oral-board-local-lab.localhost:1355'
        httpd = self.start_server(origin)
        self.assertEqual(self.request(httpd, 'fix-ui.oral-board-local-lab.localhost:1355', origin), 200)
        self.assertEqual(self.request(httpd, 'other.oral-board-local-lab.localhost:1355', origin), 403)
        self.assertEqual(self.request(httpd, 'fix-ui.oral-board-local-lab.localhost', origin), 403)


if __name__ == '__main__':
    unittest.main()

class ServerFailureTests(ServerOriginTests):
    def test_missing_and_corrupt_saved_results_return_json(self):
        import json
        with tempfile.TemporaryDirectory() as temporary, patch('server.ROOT', Path(temporary)):
            root = Path(temporary)
            httpd = self.start_server()
            for value in (None, '{'):
                if value is not None:
                    (root / 'runs').mkdir(exist_ok=True)
                    (root / 'runs/results.json').write_text(value)
                connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=2)
                self.addCleanup(connection.close)
                connection.request('GET', '/api/results')
                response = connection.getresponse()
                self.assertEqual(response.status, 503)
                self.assertIn('error', json.loads(response.read()))

    def test_invalid_run_types_return_json_and_release_inference_slot(self):
        import json
        import server
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / '.local').mkdir()
        (root / '.local/development-run-history.json').write_text('{}')
        fixture = patch('server.ROOT', root)
        fixture.start()
        self.addCleanup(fixture.stop)
        httpd = self.start_server()
        for run in ([], {}, 42):
            connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=2)
            self.addCleanup(connection.close)
            connection.request('POST', '/api/development/predict', json.dumps({'run': run}))
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn('error', json.loads(response.read()))
            self.assertFalse(server.BUSY.locked())

    def test_partial_body_times_out_and_releases_slot(self):
        import json
        import server
        with patch.object(server.Handler, 'request_timeout', 0.1):
            httpd = self.start_server()
            connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=2)
            self.addCleanup(connection.close)
            connection.putrequest('POST', '/api/predict')
            connection.putheader('Content-Length', '20')
            connection.endheaders(b'{')
            response = connection.getresponse()
            self.assertEqual(response.status, 408)
            self.assertIn('error', json.loads(response.read()))
            self.assertFalse(server.BUSY.locked())
            self.assertEqual(self.request(httpd), 200)
