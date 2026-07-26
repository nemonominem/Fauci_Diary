#!/usr/bin/env python3
"""
Local web server for the Tony's Diary search app.
Serves the diary JSON, page map, and the original PDF.
"""

import http.server
import socketserver
import os

PORT = 8765
DIRECTORY = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('localhost', PORT), Handler) as httpd:
        print(f'Serving diary search app at http://localhost:{PORT}')
        print(f'Directory: {DIRECTORY}')
        print('Press Ctrl+C to stop.')
        httpd.serve_forever()
