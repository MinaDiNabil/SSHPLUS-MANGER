#!/usr/bin/env python3
# encoding: utf-8
# SSHPLUS By @Crazy_vpn
import socket
import threading
import select
import sys
import os
import time

WSPROXY_DEBUG_LOG = os.environ.get('WSPROXY_DEBUG_LOG', '0') == '1'

IP = '0.0.0.0'
try:
    PORT = int(sys.argv[1])
except (IndexError, ValueError):
    PORT = 8080
PASS = ''
BUFLEN = 8196 * 8
TIMEOUT = 60
MSG = 'ALERT'
DEFAULT_HOST = '0.0.0.0:1194'
RESPONSE = ("HTTP/1.1 101 " + str(MSG) + "\r\n\r\n").encode('utf-8')


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
        # SO_REUSEPORT lets multiple open.py instances share the same
        # bind() so the kernel load-balances accept() across processes.
        try:
            self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        self.soc.settimeout(2)
        self.soc.bind((self.host, self.port))
        # Listen backlog matches net.core.somaxconn from the install
        # tuning so reconnect storms don't spill to "connection refused".
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
        # Production no-op — see Modulos/wsproxy.py for the rationale.
        # Set WSPROXY_DEBUG_LOG=1 in env to re-enable.
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
        self.log = 'Conexao: ' + str(addr)
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
            self.client_buffer = self.client.recv(BUFLEN).decode('utf-8', errors='replace')

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
                elif hostPort.startswith(IP):
                    self.method_CONNECT(hostPort)
                else:
                    self.client.send(b'HTTP/1.1 403 Forbidden!\r\n\r\n')
            else:
                print('- No X-Real-Host!')
                self.client.send(b'HTTP/1.1 400 NoXRealHost!\r\n\r\n')

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
                port = 22

        (soc_family, soc_type, proto, _, address) = socket.getaddrinfo(host, port)[0]

        self.target = socket.socket(soc_family, soc_type, proto)
        self.target.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        try:
            self.target.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except (AttributeError, OSError):
            pass
        self.targetClosed = False
        self.target.connect(address)

    def method_CONNECT(self, path):
        self.method = 'CONNECT'
        self.log += ' - CONNECT ' + path
        self.connect_target(path)
        self.client.sendall(RESPONSE)
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


def main(host=IP, port=PORT):
    print("\033[0;34m" + "━" * 8 + " \033[1;32mPROXY SOCKS\033[0;34m " + "━" * 8 + "\n")
    print("\033[1;33mIP:\033[1;32m " + IP)
    print("\033[1;33mPORTA:\033[1;32m " + str(PORT) + "\n")
    print("\033[0;34m" + "━" * 10 + " \033[1;32mSSHPLUS\033[0;34m " + "━\033[1;37m" * 11 + "\n")
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
