"""Exercise the demo's HTTP boundary with synthetic requests and no inference."""
import http.client
import threading
import unittest

from server import make_server


class ServerOriginTests(unittest.TestCase):
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

    def test_invalid_proxy_origins_are_rejected_before_binding(self):
        for origin in [
            'https://example.com',
            'https://oral-board-local-lab.local',
            'ftp://oral-board-local-lab.localhost',
            'https://user@oral-board-local-lab.localhost',
            'https://oral-board-local-lab.localhost/path',
            'https://oral-board-local-lab.localhost?query=1',
            'https://oral-board-local-lab.localhost#fragment',
            'https://oral-board-local-lab.localhost:0',
            'https://oral-board-local-lab.localhost:65536',
            'https://oral-board-local-lab.localhost:invalid',
        ]:
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError):
                    make_server(0, origin)


if __name__ == '__main__':
    unittest.main()
