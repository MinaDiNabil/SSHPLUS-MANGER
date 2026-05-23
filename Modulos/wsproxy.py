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
# Single canonical reply for every HTTP-shaped first packet.
#
# Mobile injectors (MinaProNet, HTTP Injector, HTTP Custom, ...) all
# ship a "Proxy" stage that reads our reply and then *unconditionally
# replaces* it with literally:
#   HTTP/1.0 200 Connection established\r\n\r\n
# before handing the rest of the stream to their SSH stage. We saw
# this in the user's logs as the line:
#   [PROXY] Replaced: HTTP/1.0 200 Connection Established\r\n\r\n
#
# Replying with the *same* string the injector is about to substitute
# in means:
#   - byte counts line up exactly (39 bytes in, 39 bytes out), so the
#     injector's SSH stage starts reading at the same offset on the
#     wire where our SSH banner actually starts.  Previously we sent
#     43 bytes (HTTP/1.1 101 <font ...>) and the 4-byte mismatch was
#     what the SSH stage decoded as the bogus packet length
#     1231976033 (= "Ih=!" — bytes lifted from the middle of our
#     "<font color=\"null\"></font>" reply).
#   - response code is exactly what HTTP CONNECT proxies have used
#     since the 90s, so every injector accepts it.
# Both WS Payload (GET ... Upgrade: websocket) and WS Payload+Proxy
# (CONNECT host:port) modes get the same reply; they're the same
# tunnel handshake on the wire.
RESPONSE = b"HTTP/1.0 200 Connection established\r\n\r\n"
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
        self.soc.settimeout(2)
        self.soc.bind((self.host, self.port))
        self.soc.listen(128)
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
        self.logLock.acquire()
        print(log)
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
            # right tunneling mode. Behaviour matrix, derived from
            # field testing against MinaProNet / HTTP Custom / HTTP
            # Injector logs:
            #
            #   first bytes              | mode               | reply
            #   -------------------------+--------------------+------------------
            #   CONNECT host:port ...    | WS SSL+Payload+    | HTTP/1.0 200
            #                            | Proxy              | Connection
            #                            |                    | established
            #   GET / POST / HEAD / ...  | WS SSL+Payload     | NO REPLY
            #                            | (Upgrade: websocket| (drop payload,
            #                            |  is a DPI decoy)   |  relay SSH only)
            #   SSH-2.0-... / raw TLS /  | Standard SSL TUNNEL| NO REPLY
            #   binary                   | (raw SSH-in-TLS)   | (forward as-is)
            #
            # The crucial detail: in Payload mode (GET / Upgrade:
            # websocket) the injector does NOT consume any HTTP reply
            # we send — it begins its SSH stage straight after the
            # payload write. Replying with HTTP/1.x ... \r\n\r\n then
            # made the SSH stage read 'HTTP' as the first SSH packet
            # length, giving 1213486160 = 0x48545450 = "HTTP" in the
            # "Illegal packet size!" error. Reply 0 bytes in that
            # mode and just stream SSH back, and the SSH stage gets
            # a clean banner.
            first_chunk = self.client.recv(BUFLEN)
            if not first_chunk:
                return

            is_connect = first_chunk.startswith(b'CONNECT ')
            is_other_http = (not is_connect) and any(
                first_chunk.startswith(m) for m in HTTP_METHODS
            )

            if is_connect:
                # HTTP CONNECT proxy semantics — Proxy stage WILL
                # consume the reply, then replace it for its SSH
                # stage. Send the canonical 39-byte 200 reply.
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
            elif is_other_http:
                # Payload-style decoy (GET / Upgrade: websocket).
                # Drop the payload, do NOT send any HTTP reply, just
                # bridge to the SSH backend.
                self.method = 'PAYLOAD'
                self.log += ' - PAYLOAD ' + DEFAULT_HOST
                self.connect_target(DEFAULT_HOST)
                self.client_buffer = ''
                self.server.printLog(self.log)
                self.doCONNECT()
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

    def method_CONNECT(self, path, reply=RESPONSE_WS):
        self.method = 'CONNECT'
        self.log += ' - CONNECT ' + path

        self.connect_target(path)

        # Read the SSH banner from the backend first, then send the HTTP
        # reply + banner in a single sendall(). This stops mobile
        # injectors from racing — some of them start their SSH stage as
        # soon as the Proxy stage consumes the HTTP reply, and if the
        # SSH banner hasn't arrived yet they read whatever bytes are
        # next on the wire and trip "Illegal packet size".
        first_backend = b''
        try:
            self.target.settimeout(3)
            first_backend = self.target.recv(BUFLEN)
        except (socket.timeout, OSError):
            pass
        finally:
            try:
                self.target.settimeout(None)
            except OSError:
                pass

        try:
            self.client.sendall(reply + first_backend)
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
