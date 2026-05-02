#!/usr/bin/env python3
# encoding: utf-8
import socket
import threading
import select
import sys
import time
import hashlib
import base64

IP = '0.0.0.0'
try:
    PORT = int(sys.argv[1])
except (IndexError, ValueError):
    PORT = 80
try:
    SSH_PORT = int(sys.argv[2])
except (IndexError, ValueError):
    SSH_PORT = 22
PASS = ''
BUFLEN = 8196 * 8
TIMEOUT = 60
MSG = ''
COR = '<font color="null">'
FTAG = '</font>'
DEFAULT_HOST = '127.0.0.1:' + str(SSH_PORT)
RESPONSE = "HTTP/1.1 200 " + str(COR) + str(MSG) + str(FTAG) + "\r\n\r\n"
RESPONSE_WS = "HTTP/1.1 101 " + str(COR) + str(MSG) + str(FTAG) + "\r\n\r\n"

HTTP_METHODS = (b'GET', b'POST', b'HEAD', b'PUT', b'OPTIONS', b'DELETE', b'PATCH', b'CONNECT')
WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def ws_accept(key):
    digest = hashlib.sha1((key + WS_GUID).encode('ascii')).digest()
    return base64.b64encode(digest).decode('ascii')


class Server(threading.Thread):
    def __init__(self, host, port):
        threading.Thread.__init__(self)
        self.running = False
        self.host = host
        self.port = port
        self.threads = []
        self.threadsLock = threading.Lock()

    def run(self):
        self.soc = socket.socket(socket.AF_INET)
        self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.soc.settimeout(2)
        self.soc.bind((self.host, self.port))
        self.soc.listen(0)
        self.running = True

        try:
            while self.running:
                try:
                    c, addr = self.soc.accept()
                    c.setblocking(1)
                except socket.timeout:
                    continue

                conn = ConnectionHandler(c, self, addr)
                conn.start()
                self.addConn(conn)
        finally:
            self.running = False
            self.soc.close()

    def addConn(self, conn):
        try:
            self.threadsLock.acquire()
            if self.running:
                self.threads.append(conn)
        finally:
            self.threadsLock.release()

    def removeConn(self, conn):
        try:
            self.threadsLock.acquire()
            if conn in self.threads:
                self.threads.remove(conn)
        finally:
            self.threadsLock.release()

    def close(self):
        try:
            self.running = False
            self.threadsLock.acquire()
            threads = list(self.threads)
            for c in threads:
                c.close()
        finally:
            self.threadsLock.release()


class ConnectionHandler(threading.Thread):
    def __init__(self, socClient, server, addr):
        threading.Thread.__init__(self)
        self.clientClosed = False
        self.targetClosed = True
        self.client = socClient
        self.client_buffer = ''
        self.server = server

    def close(self):
        try:
            if not self.clientClosed:
                self.client.shutdown(socket.SHUT_RDWR)
                self.client.close()
        except Exception:
            pass
        finally:
            self.clientClosed = True

        try:
            if not self.targetClosed:
                self.target.shutdown(socket.SHUT_RDWR)
                self.target.close()
        except Exception:
            pass
        finally:
            self.targetClosed = True

    def _classify(self, raw):
        # 'raw'     -> non-HTTP (e.g. SSH greeting), tunnel as-is
        # 'connect' -> HTTP CONNECT proxy
        # 'ws'      -> any other HTTP request (treated as WebSocket-style payload)
        if not raw:
            return 'raw'
        head = raw.split(b'\r\n', 1)[0]
        parts = head.split(b' ')
        if len(parts) < 3 or not parts[-1].startswith(b'HTTP/'):
            return 'raw'
        if parts[0].upper() not in HTTP_METHODS:
            return 'raw'
        if parts[0].upper() == b'CONNECT':
            return 'connect'
        return 'ws'

    def _ws_handshake_response(self):
        ws_key = self.findHeader(self.client_buffer, 'Sec-WebSocket-Key')
        if ws_key:
            ws_proto = self.findHeader(self.client_buffer, 'Sec-WebSocket-Protocol')
            lines = [
                'HTTP/1.1 101 Switching Protocols',
                'Upgrade: websocket',
                'Connection: Upgrade',
                'Sec-WebSocket-Accept: ' + ws_accept(ws_key),
            ]
            if ws_proto:
                lines.append('Sec-WebSocket-Protocol: ' + ws_proto.split(',')[0].strip())
            return ('\r\n'.join(lines) + '\r\n\r\n').encode('utf-8')
        return RESPONSE_WS.encode('utf-8')

    def run(self):
        try:
            # Server-speaks-first protocols (raw SSH): use a short read window
            # to detect that case so we don't deadlock waiting for the client.
            self.client.settimeout(0.5)
            try:
                raw = self.client.recv(BUFLEN)
            except socket.timeout:
                raw = b''
            finally:
                self.client.settimeout(None)
            kind = self._classify(raw)

            if kind == 'raw':
                # Raw payload (or no payload yet, client awaits server banner).
                self.method = 'RAW'
                self.connect_target(DEFAULT_HOST)
                if raw:
                    try:
                        self.target.sendall(raw)
                    except Exception:
                        pass
                self.client_buffer = ''
                self.doCONNECT()
                return

            try:
                self.client_buffer = raw.decode('utf-8', errors='ignore')
            except Exception:
                self.client_buffer = ''

            if kind == 'connect':
                head = self.client_buffer.split('\r\n', 1)[0]
                target = head.split(' ')[1] if ' ' in head else DEFAULT_HOST
                passwd = self.findHeader(self.client_buffer, 'X-Pass')
                if len(PASS) != 0 and passwd != PASS:
                    self.client.send(b'HTTP/1.1 407 Proxy Authentication Required\r\n\r\n')
                    return
                # Force the local SSH backend regardless of the requested host
                # to avoid open-proxy abuse.
                host_only = target.split(':', 1)[0]
                if host_only not in ('127.0.0.1', 'localhost', IP):
                    target = DEFAULT_HOST
                self.method = 'CONNECT'
                self.connect_target(target)
                self.client.sendall(RESPONSE.encode('utf-8'))
                self.client_buffer = ''
                self.doCONNECT()
                return

            # kind == 'ws': WebSocket / payload upgrade.
            hostPort = self.findHeader(self.client_buffer, 'X-Real-Host')
            if hostPort == '':
                hostPort = DEFAULT_HOST

            split = self.findHeader(self.client_buffer, 'X-Split')
            if split != '':
                self.client.recv(BUFLEN)

            passwd = self.findHeader(self.client_buffer, 'X-Pass')
            if len(PASS) != 0 and passwd == PASS:
                self.method_CONNECT(hostPort)
            elif len(PASS) != 0 and passwd != PASS:
                self.client.send(b'HTTP/1.1 400 WrongPass!\r\n\r\n')
            else:
                # Mobile tunneling apps usually put the server's public IP or
                # domain in X-Real-Host. Always target the local SSH backend
                # regardless of what the client sent, instead of replying 403.
                if not (hostPort.startswith('127.0.0.1')
                        or hostPort.startswith('localhost')
                        or hostPort.startswith(IP)):
                    hostPort = DEFAULT_HOST
                self.method_CONNECT(hostPort)

        except Exception:
            pass
        finally:
            self.close()
            self.server.removeConn(self)

    def findHeader(self, head, header):
        aux = head.find(header + ': ')

        if aux == -1:
            return ''

        aux = head.find(':', aux)
        head = head[aux + 2:]
        aux = head.find('\r\n')

        if aux == -1:
            return ''

        return head[:aux]

    def connect_target(self, host):
        i = host.find(':')
        if i != -1:
            port = int(host[i + 1:])
            host = host[:i]
        else:
            if getattr(self, 'method', '') == 'CONNECT':
                port = 443
            else:
                port = 22

        (soc_family, soc_type, proto, _, address) = socket.getaddrinfo(host, port)[0]

        self.target = socket.socket(soc_family, soc_type, proto)
        self.targetClosed = False
        self.target.connect(address)

    def method_CONNECT(self, path):
        self.method = 'CONNECT'
        self.connect_target(path)
        self.client.sendall(self._ws_handshake_response())
        self.client_buffer = ''
        self.doCONNECT()

    def doCONNECT(self):
        socs = [self.client, self.target]
        count = 0
        error = False
        while True:
            count += 1
            (recv, _, err) = select.select(socs, [], socs, 3)
            if err:
                error = True
            if recv:
                for in_ in recv:
                    try:
                        data = in_.recv(BUFLEN)
                        if data:
                            if in_ is self.target:
                                self.client.send(data)
                            else:
                                while data:
                                    byte = self.target.send(data)
                                    data = data[byte:]
                            count = 0
                        else:
                            break
                    except Exception:
                        error = True
                        break
            if count == TIMEOUT:
                error = True

            if error:
                break


def main(host=IP, port=PORT):
    print("\033[0;34m━" * 8, "\033[1;32m PROXY SOCKS", "\033[0;34m━" * 8, "\n")
    print("\033[1;33mIP:\033[1;32m " + IP)
    print("\033[1;33mPORTA:\033[1;32m " + str(PORT) + "\n")
    print("\033[0;34m━" * 10, "\033[1;32m SSHPLUS", "\033[0;34m━\033[1;37m" * 11, "\n")
    server = Server(IP, PORT)
    server.start()
    while True:
        try:
            time.sleep(2)
        except KeyboardInterrupt:
            print('\nParando...')
            server.close()
            break


if __name__ == '__main__':
    main()
