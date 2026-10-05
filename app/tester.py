from __future__ import annotations
import asyncio, time
from typing import Any
from .config import clone_for_target, server_values
from .models import Target, TestResult
from .payload import render_payload
from .transports import ssh_direct, ssh_via_http_proxy, ssh_via_tls


def mode(network: dict[str, Any]) -> str:
    text = ' '.join(str(network.get(k, '')) for k in ('TYPE','Mode','TunnelType','Info','Name')).upper()
    if any(x in text for x in ('SSL_PROXY','SSH_SSL','TLS','SSL')):
        return 'tls'
    if any(x in text for x in ('SSH_PROXY','HTTP_PROXY','PROXY')):
        return 'proxy'
    # A populated ProxyIP/ProxyPort is also a strong indication of proxy mode.
    if network.get('ProxyIP') or network.get('ProxyPort'):
        return 'proxy'
    return 'direct'


def one(network, server_cfg, target, timeout):
    started = time.monotonic()
    cfg = clone_for_target(network, target.kind, target.value)
    server, server_port, user, password, ssl_port = server_values(server_cfg)
    try:
        payload = render_payload(cfg.get('Payload',''), server, server_port)
        m = mode(cfg)
        if target.kind == 'ip':
            proxy = str(cfg.get('ProxyIP') or target.value)
            proxy_port = int(cfg.get('ProxyPort') or 80)
            if m == 'tls':
                sni = str(cfg.get('SNI') or server)
                tls_ip = str(cfg.get('TlsIP') or proxy)
                result = ssh_via_tls(tls_ip, 443, sni, server, server_port, user, password, timeout, payload)
            elif m == 'proxy':
                result = ssh_via_http_proxy(proxy, proxy_port, server, server_port, user, password, timeout, payload)
            else:
                # Para configurações sem proxy, o IP fornecido não substitui o servidor.
                result = ssh_direct(server, server_port, user, password, timeout)
        else:
            # Domínio recebido sempre é aplicado como SNI e testado em TLS/443.
            sni = target.value
            tls_ip = str(cfg.get('TlsIP') or cfg.get('ProxyIP') or server)
            result = ssh_via_tls(tls_ip, 443, sni, server, server_port, user, password, timeout, payload)
        status, reason = result.status, result.reason
    except TimeoutError as e:
        status, reason = 'timeout', str(e) or 'timeout'
    except Exception as e:
        msg = str(e) or type(e).__name__
        low = msg.lower()
        if 'timed out' in low or 'timeout' in low:
            status = 'timeout'
        elif 'authentication' in low or 'auth' in low or 'permission denied' in low:
            status = 'auth_failed'
        else:
            status = 'error'
        reason = msg
    elapsed = int((time.monotonic()-started)*1000)
    return TestResult(status, target.kind, target.value, server, server_port, str(network.get('Name','')), elapsed, reason, cfg)


def socket_timeout_error():
    import socket
    return socket.timeout


async def run_batch(cfg, targets, timeout=12, concurrency=10, on_result=None):
    sem = asyncio.Semaphore(concurrency)
    results=[]
    async def task(network, server, target):
        async with sem:
            r = await asyncio.to_thread(one, network, server, target, timeout)
            results.append(r)
            if on_result:
                await on_result(r)
    jobs=[task(n,s,t) for s in cfg['Networks'] for s in cfg['Servers'] for t in targets]
    await asyncio.gather(*jobs)
    return results
