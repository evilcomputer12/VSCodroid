#!/usr/bin/env python3
"""Real stdio LSP round trip; run inside the Debian workspace."""
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

source = Path.cwd() / 'clangd-smoke.c'
source.write_text('int square(int value) { return value * value; }\nint main(void) { return square(7); }\n')
uri = source.as_uri()
messages = queue.Queue()
with open('clangd-smoke.stderr', 'wb') as errors:
    process = subprocess.Popen(['clangd', '--background-index=0', '-j=1'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
    def reader():
        try:
            while True:
                headers = {}
                while True:
                    line = process.stdout.readline()
                    if not line:
                        raise EOFError('clangd closed stdout')
                    if line == b'\r\n':
                        break
                    name, value = line.decode().split(':', 1)
                    headers[name.lower()] = value.strip()
                messages.put(json.loads(process.stdout.read(int(headers['content-length']))))
        except Exception as error:
            messages.put(error)
    threading.Thread(target=reader, daemon=True).start()
    def send(message):
        payload = json.dumps(dict(jsonrpc='2.0', **message)).encode()
        process.stdin.write(f'Content-Length: {len(payload)}\r\n\r\n'.encode() + payload)
        process.stdin.flush()
    def request(number, method, params):
        send(dict(id=number, method=method, params=params))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            message = messages.get(timeout=max(0.1, deadline - time.monotonic()))
            if isinstance(message, Exception):
                raise message
            if message.get('id') == number:
                if 'error' in message:
                    raise RuntimeError(message['error'])
                return message.get('result')
        raise TimeoutError(method)
    try:
        initialized = request(1, 'initialize', dict(processId=None, rootUri=Path.cwd().as_uri(), capabilities={}))
        assert initialized['capabilities']['hoverProvider']
        send(dict(method='initialized', params={}))
        send(dict(method='textDocument/didOpen', params=dict(textDocument=dict(
            uri=uri, languageId='c', version=1, text=source.read_text()))))
        position = dict(textDocument=dict(uri=uri), position=dict(line=1, character=25))
        hover = request(2, 'textDocument/hover', position)
        definition = request(3, 'textDocument/definition', position)
        assert 'square' in json.dumps(hover), hover
        assert definition and definition[0]['range']['start']['line'] == 0, definition
        request(4, 'shutdown', None)
        send(dict(method='exit', params=None))
        assert process.wait(timeout=10) == 0
        print(json.dumps(dict(clangdInitialize=True, hover=True, definition=True, uri=uri)))
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
