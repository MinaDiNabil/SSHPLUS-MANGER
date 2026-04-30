#!/usr/bin/env python3
# encoding: utf-8
import socket
import threading
import select
import sys
import time
import getopt

PASS = ''
LISTENING_ADDR = '0.0.0.0'
try:
    LISTENING_PORT = int(sys.argv[1])
except (IndexError, ValueError):
    LISTENING_PORT = 80
try:
    SSH_PORT = int(sys.argv[2])
except (IndexError, ValueError):
    SSH_PORT = 22
BUFLEN = 4096 * 4
TIMEOUT = 60
MSG = ''
COR = '<font color="null">'
FTAG = '</font>'
DEFAULT_HOST = "127.0.0.1:" + str(SSH_PORT)
RESPONSE_WS = "HTTP/1.1 101 " + str(COR) + str(MSG) + str(FTAG) + "\r\n\r\n"
RESPONSE_PROXY = "HTTP/1.1 200 " + str(COR) + str(MSG) + str(FTAG) + "\r\n\r\n"

HTTP_METHODS = (b'GET', b'POST', b'HEAD', b'PUT', b'OPTIONS', b'DELETE', b'PATCH', b'CONNECT')


class Server(threading.Thread):
    def __init__(self, host, port):
        threading.Thread.__init__(self)
        self.running = False
        self.host = host
        self.port = port
        self.threads = []
        self.threadsLock = threading.Lock()
        self.logLock = threading.Lock()

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

    def printLog(self, log):
        with self.logLock:
            print(log)

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
        self.log = 'Connection: ' + str(addr)

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
        # Returns one of: 'raw', 'connect', 'ws'
        # 'raw'     -> non-HTTP (e.g. SSH greeting "SSH-2.0-...") tunnel as-is
        # 'connect' -> standard HTTP CONNECT proxy ("CONNECT host:port HTTP/1.1")
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

    def run(self):
        try:
            raw = self.client.recv(BUFLEN)
            kind = self._classify(raw)

            if kind == 'raw':
                # Non-HTTP payload (raw SSH inside SSL/TLS tunnel, etc.)
                # Forward unmodified to the default backend without sending any HTTP response.
                self.method = 'RAW'
                self.log += ' - RAW ' + DEFAULT_HOST
                self.connect_target(DEFAULT_HOST)
                try:
                    self.target.sendall(raw)
                except Exception:
                    pass
                self.client_buffer = ''
                self.server.printLog(self.log)
                self.doCONNECT()
                return

            try:
                self.client_buffer = raw.decode('utf-8', errors='ignore')
            except Exception:
                self.client_buffer = ''

            if kind == 'connect':
                # Standard HTTP CONNECT proxy (Payload + SSL/TLS + Proxy = WS Proxy)
                head = self.client_buffer.split('\r\n', 1)[0]
                target = head.split(' ')[1] if ' ' in head else DEFAULT_HOST
                # Optional auth via X-Pass header
                passwd = self.findHeader(self.client_buffer, 'X-Pass')
                if len(PASS) != 0 and passwd != PASS:
                    self.client.send(b'HTTP/1.1 407 Proxy Authentication Required\r\n\r\n')
                    return
                # Restrict to localhost backends to avoid open-proxy abuse
                host_only = target.split(':', 1)[0]
                if host_only not in ('127.0.0.1', 'localhost', LISTENING_ADDR):
                    target = DEFAULT_HOST
                self.method = 'CONNECT'
                self.log += ' - CONNECT ' + target
                self.connect_target(target)
                self.client.sendall(RESPONSE_PROXY.encode('utf-8'))
                self.client_buffer = ''
                self.server.printLog(self.log)
                self.doCONNECT()
                return

            # kind == 'ws' -> Payload + SSL/TLS = WS SSL (and plain WebSocket payloads)
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
            elif hostPort.startswith('127.0.0.1') or hostPort.startswith('localhost'):
                self.method_CONNECT(hostPort)
            else:
                self.client.send(b'HTTP/1.1 403 Forbidden!\r\n\r\n')

        except Exception as e:
            self.log += ' - error: ' + str(e)
            self.server.printLog(self.log)
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
                port = 80

        (soc_family, soc_type, proto, _, address) = socket.getaddrinfo(host, port)[0]

        self.target = socket.socket(soc_family, soc_type, proto)
        self.targetClosed = False
        self.target.connect(address)

    def method_CONNECT(self, path):
        self.method = 'CONNECT'
        self.log += ' - WS ' + path

        self.connect_target(path)
        self.client.sendall(RESPONSE_WS.encode('utf-8'))
        self.client_buffer = ''

        self.server.printLog(self.log)
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


def print_usage():
    print('Use: proxy.py -p <port>')
    print('       proxy.py -b <ip> -p <porta>')
    print('       proxy.py -b 0.0.0.0 -p 22')


def parse_args(argv):
    global LISTENING_ADDR
    global LISTENING_PORT

    try:
        opts, args = getopt.getopt(argv, "hb:p:", ["bind=", "port="])
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print_usage()
            sys.exit()
        elif opt in ("-b", "--bind"):
            LISTENING_ADDR = arg
        elif opt in ("-p", "--port"):
            LISTENING_PORT = int(arg)


def main(host=LISTENING_ADDR, port=LISTENING_PORT):
    print("\033[0;34m━" * 8, "\033[1;32m PROXY WEBSOCKET", "\033[0;34m━" * 8, "\n")
    print("\033[1;33mIP:\033[1;32m " + LISTENING_ADDR)
    print("\033[1;33mPORTA:\033[1;32m " + str(LISTENING_PORT) + "\n")
    print("\033[0;34m━" * 10, "\033[1;32m VPSMANAGER", "\033[0;34m━\033[1;37m" * 11, "\n")

    server = Server(LISTENING_ADDR, LISTENING_PORT)
    server.start()

    while True:
        try:
            time.sleep(2)
        except KeyboardInterrupt:
            print('Parando...')
            server.close()
            break


if __name__ == '__main__':
    main()
