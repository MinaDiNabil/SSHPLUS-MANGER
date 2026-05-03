#!/usr/bin/env python3
# encoding: utf-8
"""
Dynamic per-SNI TLS terminator. Drop-in replacement for stunnel on the
SSL TUNNEL listener. For every incoming TLS connection it sniffs the
SNI hostname from the ClientHello, hands ssl.SSLContext a freshly
issued leaf certificate whose CN/SAN matches that hostname, and
forwards the decrypted plaintext to a backend (typically the wsproxy
multiplexer on 127.0.0.1).

Why this exists:
A static cert (which is what stunnel uses) only ever covers a fixed
list of names. Mobile injectors that piggy-back on zero-rated bug
hosts (paysecure.islamicbank.ps, *.gateway.mastercard.com, hcaptcha
endpoints, ...) put those hosts in the TLS SNI to bypass carrier
billing. Strict TLS clients and carrier middleboxes reject any
handshake where the server cert does not cover the SNI, so adding
each new bug host to the cert SAN by hand is an endless game of
whack-a-mole. Issuing a leaf cert on the fly that matches whatever
SNI showed up in the ClientHello solves the problem definitively:
the cert is *always* a match.

Certs are signed by a long-lived self-signed CA stored in /etc/stunnel
and cached on disk so repeated connects to the same SNI reuse a
single cert.

Usage:
  sniproxy.py <listen_port> <backend_port>
  sniproxy.py <listen_port> <backend_port> --bind 0.0.0.0
"""

import argparse
import os
import re
import select
import socket
import ssl
import subprocess
import sys
import threading
import time

CA_DIR       = '/etc/stunnel'
CA_KEY       = os.path.join(CA_DIR, 'sniproxy_ca.key')
CA_CERT      = os.path.join(CA_DIR, 'sniproxy_ca.crt')
CACHE_DIR    = os.path.join(CA_DIR, 'sni_cache')
DEFAULT_KEY  = os.path.join(CA_DIR, 'sniproxy_default.key')
DEFAULT_CERT = os.path.join(CA_DIR, 'sniproxy_default.crt')

BUFLEN            = 65536
HANDSHAKE_TIMEOUT = 10
PIPE_TIMEOUT      = 60

# Hostname grammar from RFC 1123/5890: labels of [a-z0-9-] separated
# by dots, total length <= 253. Refuses anything else (control chars,
# slashes, ..) so the value is safe to use as a filename and as an
# openssl CN.
_HOSTNAME_RE = re.compile(
    r'^(?=.{1,253}$)'
    r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*'
    r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'
)

_cert_lock = threading.Lock()


def _run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def ensure_ca():
    """Create the per-host self-signed CA and the default leaf cert.

    Idempotent; re-running is cheap when both files already exist."""
    os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
    try:
        os.chmod(CACHE_DIR, 0o700)
    except OSError:
        pass
    if not (os.path.exists(CA_KEY) and os.path.exists(CA_CERT)):
        cnf = os.path.join(CA_DIR, '_sniproxy_ca.cnf')
        with open(cnf, 'w') as f:
            f.write(
                "[req]\n"
                "default_bits = 2048\n"
                "prompt = no\n"
                "default_md = sha256\n"
                "distinguished_name = dn\n"
                "x509_extensions = v3_ca\n"
                "[dn]\n"
                "CN = SSHPlus Dynamic SNI CA\n"
                "[v3_ca]\n"
                "basicConstraints = critical, CA:TRUE, pathlen:0\n"
                "keyUsage = critical, digitalSignature, keyCertSign, cRLSign\n"
            )
        _run([
            'openssl', 'req', '-x509', '-nodes', '-days', '3650',
            '-newkey', 'rsa:2048',
            '-keyout', CA_KEY,
            '-out', CA_CERT,
            '-config', cnf,
            '-extensions', 'v3_ca',
        ])
        try:
            os.chmod(CA_KEY, 0o600)
        except OSError:
            pass
        try:
            os.unlink(cnf)
        except OSError:
            pass


def _normalize_sni(sni):
    """Return a usable hostname or None."""
    if not sni:
        return None
    sni = sni.strip().rstrip('.').lower()
    if not _HOSTNAME_RE.match(sni):
        return None
    return sni


def _cert_paths(sni):
    safe = sni.replace('/', '_').replace('..', '_')[:200]
    return (os.path.join(CACHE_DIR, safe + '.crt'),
            os.path.join(CACHE_DIR, safe + '.key'))


def _issue_leaf(sni, cert_path, key_path):
    """Generate a fresh leaf cert for `sni` signed by the local CA.

    SAN covers both the exact hostname and a one-level wildcard for
    the parent so e.g. requesting `three-cust-imgs.hcaptcha.com` also
    serves `*.hcaptcha.com` traffic without an extra issuance."""
    cnf = cert_path + '.cnf'
    csr = cert_path + '.csr'
    sans = ['DNS.1 = ' + sni]
    if '.' in sni:
        parent = sni.split('.', 1)[1]
        if parent:
            sans.append('DNS.2 = *.' + parent)
    try:
        with open(cnf, 'w') as f:
            f.write(
                "[req]\n"
                "default_bits = 2048\n"
                "prompt = no\n"
                "default_md = sha256\n"
                "distinguished_name = dn\n"
                "req_extensions = v3_ext\n"
                "[dn]\n"
                "CN = " + sni + "\n"
                "[v3_ext]\n"
                "basicConstraints = CA:FALSE\n"
                "keyUsage = critical, digitalSignature, keyEncipherment\n"
                "extendedKeyUsage = serverAuth\n"
                "subjectAltName = @alt_names\n"
                "[alt_names]\n"
                + '\n'.join(sans) + '\n'
            )
        _run([
            'openssl', 'req', '-new', '-nodes',
            '-newkey', 'rsa:2048',
            '-keyout', key_path,
            '-out', csr,
            '-config', cnf,
        ])
        if not (os.path.exists(key_path) and os.path.exists(csr)):
            return False
        _run([
            'openssl', 'x509', '-req',
            '-in', csr,
            '-CA', CA_CERT,
            '-CAkey', CA_KEY,
            '-CAcreateserial',
            '-days', '825',
            '-sha256',
            '-out', cert_path,
            '-extfile', cnf,
            '-extensions', 'v3_ext',
        ])
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return os.path.exists(cert_path) and os.path.exists(key_path)
    finally:
        for p in (cnf, csr):
            try:
                os.unlink(p)
            except OSError:
                pass


def ensure_default_leaf():
    """Cert used when the client sends no SNI (raw IP TLS connect)."""
    if os.path.exists(DEFAULT_CERT) and os.path.exists(DEFAULT_KEY):
        return
    _issue_leaf('default.local', DEFAULT_CERT, DEFAULT_KEY)


def get_cert_for_sni(sni):
    """Return (cert_path, key_path) for `sni`, generating on demand."""
    safe = _normalize_sni(sni)
    if not safe:
        return DEFAULT_CERT, DEFAULT_KEY
    cert_path, key_path = _cert_paths(safe)
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path
    with _cert_lock:
        if not (os.path.exists(cert_path) and os.path.exists(key_path)):
            ok = False
            try:
                ok = _issue_leaf(safe, cert_path, key_path)
            except Exception:
                ok = False
            if not ok:
                return DEFAULT_CERT, DEFAULT_KEY
    return cert_path, key_path


def _sni_callback(sslsock, server_name, _ctx):
    """Swap the active SSLContext to one whose cert matches the SNI.

    Returning None signals SSL_TLSEXT_ERR_OK so the handshake
    continues with the new context's certificate."""
    try:
        cert, key = get_cert_for_sni(server_name)
        new_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        new_ctx.load_cert_chain(cert, key)
        sslsock.context = new_ctx
    except Exception:
        # Keep the default context; the handshake still completes
        # using the default cert. Better to serve a mismatched cert
        # than to abort the handshake — the injector typically
        # ignores cert validation anyway.
        pass
    return None


def _make_default_ctx():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(DEFAULT_CERT, DEFAULT_KEY)
    if hasattr(ctx, 'sni_callback'):
        ctx.sni_callback = _sni_callback
    else:
        # Python < 3.7
        ctx.set_servername_callback(_sni_callback)
    return ctx


def _pipe(a, b):
    socks = [a, b]
    try:
        while True:
            try:
                r, _, x = select.select(socks, [], socks, PIPE_TIMEOUT)
            except (select.error, OSError):
                return
            if x or not r:
                return
            for s in r:
                try:
                    data = s.recv(BUFLEN)
                except (OSError, ssl.SSLError):
                    return
                if not data:
                    return
                tgt = b if s is a else a
                try:
                    while data:
                        n = tgt.send(data)
                        if n <= 0:
                            return
                        data = data[n:]
                except (OSError, ssl.SSLError):
                    return
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


def _handle(client, ctx, backend_addr):
    backend = None
    ssock = None
    try:
        client.settimeout(HANDSHAKE_TIMEOUT)
        try:
            ssock = ctx.wrap_socket(client, server_side=True)
        except (ssl.SSLError, OSError, socket.timeout):
            try:
                client.close()
            except OSError:
                pass
            return
        ssock.settimeout(None)
        try:
            backend = socket.create_connection(backend_addr, timeout=10)
        except OSError:
            return
        backend.settimeout(None)
        _pipe(ssock, backend)
    finally:
        if ssock is not None:
            try:
                ssock.close()
            except OSError:
                pass
        else:
            try:
                client.close()
            except OSError:
                pass
        if backend is not None:
            try:
                backend.close()
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser(
        description='Dynamic SNI TLS terminator for SSHPlus SSL TUNNEL'
    )
    ap.add_argument('listen_port', type=int)
    ap.add_argument('backend_port', type=int)
    ap.add_argument('--bind', default='0.0.0.0')
    ap.add_argument('--backend-host', default='127.0.0.1')
    args = ap.parse_args()

    ensure_ca()
    ensure_default_leaf()
    ctx = _make_default_ctx()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    sock.bind((args.bind, args.listen_port))
    sock.listen(128)

    backend_addr = (args.backend_host, args.backend_port)

    print(
        "\033[0;34m" + "━" * 8
        + " \033[1;32mSNI PROXY\033[0;34m "
        + "━" * 8
    )
    print("\033[1;33mLISTEN: \033[1;32m{}:{}\033[0m".format(
        args.bind, args.listen_port
    ))
    print("\033[1;33mBACKEND: \033[1;32m{}:{}\033[0m".format(
        args.backend_host, args.backend_port
    ))

    while True:
        try:
            client, _addr = sock.accept()
        except KeyboardInterrupt:
            break
        except OSError:
            time.sleep(0.1)
            continue
        try:
            client.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_NODELAY, 1
            )
        except OSError:
            pass
        threading.Thread(
            target=_handle,
            args=(client, ctx, backend_addr),
            daemon=True,
        ).start()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
