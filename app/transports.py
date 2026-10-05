import re, socket, ssl
from dataclasses import dataclass
import paramiko

@dataclass
class Result:
    ok: bool
    status: str
    reason: str = ''


def tcp(host, port, timeout):
    s = socket.create_connection((host, int(port)), timeout=timeout)
    s.settimeout(timeout)
    return s


def recv_until(sock, marker=b'\r\n\r\n', limit=32768, timeout=5):
    old = sock.gettimeout()
    sock.settimeout(timeout)
    data = b''
    try:
        while marker not in data and len(data) < limit:
            part = sock.recv(4096)
            if not part:
                break
            data += part
    finally:
        sock.settimeout(old)
    return data


def parse_http_status(data: bytes):
    line = data.split(b'\r\n', 1)[0].decode('latin1', 'replace')
    m = re.search(r'HTTP/\d(?:\.\d)?\s+(\d{3})', line)
    return int(m.group(1)) if m else None, line


def ssh_auth(sock, username, password, timeout):
    transport = None
    try:
        transport = paramiko.Transport(sock)
        transport.banner_timeout = timeout
        transport.auth_timeout = timeout
        transport.start_client(timeout=timeout)
        transport.auth_password(username, password)
        if transport.is_authenticated():
            return Result(True, 'ok', 'SSH autenticado e conexão estabelecida')
        return Result(False, 'auth_failed', 'SSH não autenticou')
    except paramiko.AuthenticationException as e:
        return Result(False, 'auth_failed', str(e) or 'credenciais recusadas')
    except (paramiko.SSHException, EOFError, OSError) as e:
        return Result(False, 'error', str(e) or 'falha SSH')
    finally:
        if transport:
            try: transport.close()
            except Exception: pass


def ssh_direct(server, port, user, password, timeout):
    s = tcp(server, port, timeout)
    try:
        return ssh_auth(s, user, password, timeout)
    finally:
        s.close()


def ssh_via_http_proxy(proxy, proxy_port, server, server_port, user, password, timeout, payload=b''):
    s = tcp(proxy, proxy_port, timeout)
    try:
        if payload:
            s.sendall(payload)
            data = recv_until(s, timeout=min(timeout, 5))
            status, line = parse_http_status(data)
            # Se o payload foi uma requisição HTTP completa, aceitar respostas 2xx/3xx
            # como avanço do fluxo; o SSH seguinte confirma a conexão real.
            if status is not None and status >= 400:
                return Result(False, 'error', f'proxy respondeu {line}')
        else:
            req = f'CONNECT {server}:{server_port} HTTP/1.1\r\nHost: {server}:{server_port}\r\nProxy-Connection: Keep-Alive\r\n\r\n'.encode()
            s.sendall(req)
            data = recv_until(s, timeout=min(timeout, 5))
            status, line = parse_http_status(data)
            if status != 200:
                return Result(False, 'error', f'CONNECT recusado: {line}')
        return ssh_auth(s, user, password, timeout)
    finally:
        s.close()


def ssh_via_tls(tls_ip, tls_port, sni, server, server_port, user, password, timeout, payload=b''):
    raw = tcp(tls_ip, tls_port, timeout)
    try:
        ctx = ssl.create_default_context()
        # O teste valida o certificado do endpoint TLS. Se o modo real do APK aceitar
        # certificados não confiáveis, isso deve ser configurado explicitamente depois.
        tls = ctx.wrap_socket(raw, server_hostname=sni)
        try:
            if payload:
                tls.sendall(payload)
                _ = recv_until(tls, timeout=min(timeout, 5))
            return ssh_auth(tls, user, password, timeout)
        finally:
            try: tls.close()
            except Exception: pass
    finally:
        try: raw.close()
        except Exception: pass
