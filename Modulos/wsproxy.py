#!/usr/bin/env python3
# encoding: utf-8
#
# WS proxy — Python 3 port of upstream SSHPLUS wsproxy.py with
# minimal-impact stability fixes. Deliberately keeps the original's
# HTTP response format, header handling, and relay semantics so
# mobile-injector configs (MinaProNet VPN, HTTP Custom, HTTP Injector,
# etc.) trained on the upstream behaviour work unchanged.
#
# Differences from upstream worth knowing about:
#  - Python 3 syntax (print(), bytes literals, etc.) — language port
#    only, no behaviour change vs. the Python 2 original.
#  - printLog is a no-op in production. The upstream version held a
#    process-wide Lock around print() into a screen pty; under load
#    the pty's scrollback buffer could fill and the print() would
#    block indefinitely, deadlocking every handler thread. Toggle
#    with WSPROXY_DEBUG_LOG=1 in the env if you need to debug.
#  - SO_REUSEPORT is set when supported so multiple wsproxy instances
#    can share a bind and the kernel load-balances accept() across
#    them. Harmless single-instance no-op when only one is running.
#  - Optional argv[2] = backend SSH port. Defaults to 22 (matches
#    upstream's hardcoded DEFAULT_HOST). Lets the conexao "WebSocket"
#    install path pin the backend explicitly when the user has
#    multiple SSH daemons running.

import socket
import threading
import select
import sys
import time
import os
import getopt

WSPROXY_DEBUG_LOG = os.environ.get('WSPROXY_DEBUG_LOG', '0') == '1'

PASS = ''
LISTENING_ADDR = '0.0.0.0'
try:
    LISTENING_PORT = int(sys.argv[1])
except (IndexError, ValueError):
    LISTENING_PORT = 80

# Optional backend SSH port. Defaults to 22 to match upstream.
try:
    SSH_PORT = int(sys.argv[2])
except (IndexError, ValueError):
    SSH_PORT = 22

BUFLEN = 4096 * 4
TIMEOUT = 60
MSG = 'MinaProNet'
COR = '<font color="green">'
FTAG = '</font>'
DEFAULT_HOST = "127.0.0.1:" + str(SSH_PORT)

# The EXACT canonical response that upstream SSHPLUS has shipped for
# years. Mobile injectors detect WebSocket / proxy tunnels by matching
# against this byte sequence — anything else (HTTP/1.0 200 Connection
# Established, HTTP/1.1 200 OK, ...) makes injectors think the
# handshake failed and they either retry forever or kill the SSH
# stage with a connect timeout.
RESPONSE = ("HTTP/1.1 101 " + COR + MSG + FTAG + "\r\n\r\n").encode('utf-8')


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
        # Optional SO_REUSEPORT for kernel-side accept() load-balancing
        # across multiple wsproxy instances bound to the same port.
        # Harmless single-instance no-op.
        try:
            self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
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
        # Production no-op — see module docstring. Set WSPROXY_DEBUG_LOG=1
        # in env to re-enable for live debugging.
        if WSPROXY_DEBUG_LOG:
            with self.logLock:
                try:
                    print(log, flush=True)
                except (OSError, BlockingIOError):
                    pass

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
        self.client_buffer = b''
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

    def run(self):
        try:
            self.client_buffer = self.client.recv(BUFLEN)

            hostPort = self.findHeader(self.client_buffer, 'X-Real-Host')

            if hostPort == '':
                hostPort = DEFAULT_HOST

            split = self.findHeader(self.client_buffer, 'X-Split')

            if split != '':
                self.client.recv(BUFLEN)

            if hostPort != '':
                passwd = self.findHeader(self.client_buffer, 'X-Pass')

                if len(PASS) != 0 and passwd == PASS:
                    self.method_CONNECT(hostPort)
                elif len(PASS) != 0 and passwd != PASS:
                    self.client.send(b'HTTP/1.1 400 WrongPass!\r\n\r\n')
                elif hostPort.startswith('127.0.0.1') or hostPort.startswith('localhost'):
                    self.method_CONNECT(hostPort)
                else:
                    self.client.send(b'HTTP/1.1 403 Forbidden!\r\n\r\n')
            else:
                self.server.printLog('- No X-Real-Host!')
                self.client.send(b'HTTP/1.1 400 NoXRealHost!\r\n\r\n')

        except Exception as e:
            self.log += ' - error: ' + str(e)
            self.server.printLog(self.log)
        finally:
            self.close()
            self.server.removeConn(self)

    def findHeader(self, head, header):
        # head is bytes in Py3; decode lazily so we keep the bytes path
        # everywhere except this single header-search helper.
        if isinstance(head, bytes):
            try:
                head = head.decode('utf-8', errors='replace')
            except Exception:
                return ''

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
        self.log += ' - CONNECT ' + path

        self.connect_target(path)
        self.client.sendall(RESPONSE)
        self.client_buffer = b''

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
    parse_args(sys.argv[1:])
    main()
