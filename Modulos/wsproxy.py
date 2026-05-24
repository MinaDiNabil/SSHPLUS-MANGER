#!/usr/bin/env python3
# encoding: utf-8
import socket
import threading
import select
import sys
import time
import os
import getopt

# Production toggle: set WSPROXY_DEBUG_LOG=1 in env to re-enable the
# per-connection print() that used to deadlock under load.
WSPROXY_DEBUG_LOG = os.environ.get('WSPROXY_DEBUG_LOG', '0') == '1'

PASS = ''
LISTENING_ADDR = '0.0.0.0'
try:
    LISTENING_PORT = int(sys.argv[1])
except (IndexError, ValueError):
    LISTENING_PORT = 80
# Optional second positional argument is the backend SSH port. Defaults
# to 22 to match the original SSHPLUS behaviour.
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
# Reply that mobile injectors (MinaProNet, HTTP Custom, HTTP Injector,
# ...) recognise as their canonical "proxy CONNECT succeeded" string
# AND match case-sensitively against to decide whether to substitute.
#
# The injector's Proxy stage:
#   1. reads up to \r\n\r\n from the wire,
#   2. case-sensitively compares against
#      "HTTP/1.0 200 Connection Established\r\n\r\n",
#   3. if they match it consumes those bytes and lets the SSH stage
#      read the next bytes — i.e. the SSH banner;
#   4. if they don't match (different code, different wording, lower
#      case "e" instead of "E"), the bytes stay on the wire and the
#      SSH stage interprets them as its first packet header. That is
#      why every earlier attempt produced "Illegal packet size!":
#        - HTTP/1.1 101 <font ...>  →  bytes "HTTP" decoded as length
#          1213486160 (= 0x48545450) once the substitution mismatch
#          happens.
#        - HTTP/1.0 200 Connection established (lowercase 'e')  →
#          same failure, because "established" != "Established".
#
# Sending the EXACT 41-byte canonical reply makes the Proxy stage
# happy and lets the SSH stage start reading on the SSH banner.
RESPONSE = b"HTTP/1.0 200 Connection Established\r\n\r\n"
RESPONSE_WS = RESPONSE
RESPONSE_CONNECT = RESPONSE

# HTTP request lines we recognise as a payload-style handshake. Any
# other first-byte pattern (SSH-2.0, a TLS ClientHello byte 0x16, raw
# binary) is treated as a raw stream and forwarded straight to the
# SSH backend without an HTTP reply — that is what makes a single
# listener able to terminate Standard SSL TUNNEL (raw SSH inside TLS)
# AND WebSocket SSL Payload (HTTP CONNECT/GET inside TLS) on the same
# port.
HTTP_METHODS = (b'GET ', b'POST ', b'HEAD ', b'CONNECT ', b'PUT ',
                b'OPTIONS ', b'DELETE ', b'TRACE ', b'PATCH ')


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
        self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # SO_REUSEPORT lets multiple wsproxy instances share the same
        # bind() so the kernel load-balances accept() across processes
        # — required for 1M+ user installations where a single Python
        # thread-per-connection process tops out around 5K concurrent.
        try:
            self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        self.soc.settimeout(2)
        self.soc.bind((self.host, self.port))
        # Listen backlog matches net.core.somaxconn from the install
        # tuning. The previous value of 128 capped burst arrival at
        # ~128 SYN-ACK'd connections per second, which manifested as
        # "connection refused" spikes whenever 1K+ users reconnected
        # together after a brief upstream blip.
        self.soc.listen(65535)
        self.running = True

        try:
            while self.running:
                try:
                    c, addr = self.soc.accept()
                    c.setblocking(1)
                    c.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    try:
                        c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    except (AttributeError, OSError):
                        pass
                except socket.timeout:
                    continue
                except OSError:
                    continue

                conn = ConnectionHandler(c, self, addr)
                conn.daemon = True
                conn.start()
                self.addConn(conn)
        finally:
            self.running = False
            self.soc.close()

    def printLog(self, log):
        # No-op in production. At 5K+ connections/sec, holding a global
        # lock and calling print() into a possibly-detached screen pty
        # was the dominant GIL serialisation point in this process —
        # and could deadlock every worker thread if the screen pty
        # buffer filled up. The log content is debug-only and is not
        # consumed by anything in the management toolkit. Toggle by
        # setting environment variable WSPROXY_DEBUG_LOG=1 if needed.
        if WSPROXY_DEBUG_LOG:
            self.logLock.acquire()
            try:
                print(log, flush=True)
            except (OSError, BlockingIOError):
                pass
            finally:
                self.logLock.release()

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
        self.method = ''

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
            # Peek at the first bytes from the client and pick the
            # right tunneling mode:
            #
            #   first bytes              | mode               | reply
            #   -------------------------+--------------------+--------------------
            #   CONNECT host:port ...    | WS SSL+Payload+    | "HTTP/1.0 200
            #                            | Proxy              |  Connection
            #                            |                    |  Established\r\n\r\n"
            #   GET / POST / HEAD / ...  | WS SSL+Payload     | same as above
            #                            |                    | (injector still
            #                            |                    |  expects an HTTP
            #                            |                    |  response and
            #                            |                    |  consumes it before
            #                            |                    |  SSH stage starts)
            #   SSH-2.0-... / raw TLS    | Standard SSL TUNNEL| no reply, forward
            #                            | (raw SSH-in-TLS)   | first chunk as-is
            #
            # Why the EXACT phrase
            # "HTTP/1.0 200 Connection Established\r\n\r\n" matters:
            # the injector's Proxy stage does a CASE-SENSITIVE match
            # against this string. If the reply matches verbatim, the
            # Proxy stage consumes those 41 bytes off the wire and
            # the SSH stage starts reading at the SSH banner. If the
            # reply differs by even one character (lower-case 'e' in
            # "established", or "HTTP/1.1 101 ..." instead of 200),
            # the bytes stay on the wire, the SSH stage decodes them
            # as a packet header, and we get
            # "Illegal packet size!" with whatever 4 bytes were at
            # the start of our reply (1213486160 = "HTTP",
            # 1231976033 = "Ih=!", etc.).
            first_chunk = self.client.recv(BUFLEN)
            if not first_chunk:
                return

            is_http = any(first_chunk.startswith(m) for m in HTTP_METHODS)

            if is_http:
                self.client_buffer = first_chunk.decode('utf-8', errors='replace')

                hostPort = self.findHeader(self.client_buffer, 'X-Real-Host')
                if hostPort == '':
                    hostPort = DEFAULT_HOST

                split = self.findHeader(self.client_buffer, 'X-Split')
                if split != '':
                    self.client.recv(BUFLEN)

                passwd = self.findHeader(self.client_buffer, 'X-Pass')
                if len(PASS) != 0 and passwd != PASS:
                    self.client.send(b'HTTP/1.1 400 WrongPass!\r\n\r\n')
                else:
                    self.method_CONNECT(hostPort, RESPONSE)
            else:
                # Raw stream — forward to SSH without an HTTP reply.
                self.method = 'TUNNEL'
                self.log += ' - RAW ' + DEFAULT_HOST
                self.connect_target(DEFAULT_HOST)
                self.target.sendall(first_chunk)
                self.client_buffer = ''
                self.server.printLog(self.log)
                self.doCONNECT()

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
            if self.method == 'CONNECT':
                port = 443
            else:
                port = 80

        (soc_family, soc_type, proto, _, address) = socket.getaddrinfo(host, port)[0]

        self.target = socket.socket(soc_family, soc_type, proto)
        self.target.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        try:
            self.target.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except (AttributeError, OSError):
            pass
        self.targetClosed = False
        self.target.connect(address)

    def method_CONNECT(self, path, reply=RESPONSE):
        self.method = 'CONNECT'
        self.log += ' - CONNECT ' + path

        self.connect_target(path)
        # Send ONLY the HTTP reply here. The SSH banner comes from
        # the backend through the doCONNECT relay loop. Bundling them
        # in a single sendall() turned out to feed the injector's SSH
        # stage stray bytes from the reply tail (the source of every
        # earlier "Illegal packet size" value: 1213486160 = "HTTP",
        # 1231976033 = "Ih=!", ...) — keeping the reply alone lets
        # the Proxy stage's case-sensitive consume cleanly delimit
        # where SSH actually starts.
        try:
            self.client.sendall(reply)
        except OSError:
            pass

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
    print("\033[0;34m" + "━" * 8 + " \033[1;32mPROXY WEBSOCKET\033[0;34m " + "━" * 8 + "\n")
    print("\033[1;33mIP:\033[1;32m " + LISTENING_ADDR)
    print("\033[1;33mPORTA:\033[1;32m " + str(LISTENING_PORT) + "\n")
    print("\033[0;34m" + "━" * 10 + " \033[1;32mVPSMANAGER\033[0;34m " + "━\033[1;37m" * 11 + "\n")

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
