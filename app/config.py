import copy, json
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('config.json deve ser um objeto JSON')
    data.setdefault('Servers', [])
    data.setdefault('Networks', [])
    if not data['Servers']:
        raise ValueError('config.json não possui Servers')
    if not data['Networks']:
        raise ValueError('config.json não possui Networks')
    return data


def clone_for_target(network: dict[str, Any], target_kind: str, target: str) -> dict[str, Any]:
    c = copy.deepcopy(network)
    if target_kind == 'ip':
        c['ProxyIP'] = target
        c['ProxyPort'] = '80'
    elif target_kind == 'sni':
        c['SNI'] = target
        c['_test_tls_port'] = 443
    else:
        raise ValueError(f'tipo de alvo inválido: {target_kind}')
    return c


def server_values(server: dict[str, Any]):
    host = str(server.get('ServerIP') or server.get('server_host') or '').strip()
    port = int(server.get('ServerPort') or server.get('server_port') or 22)
    user = str(server.get('USER') or server.get('username') or '')
    password = str(server.get('PASS') or server.get('password') or '')
    ssl_port = int(server.get('SSLPort') or 443)
    if not host:
        raise ValueError('ServerIP vazio')
    if not user or not password:
        raise ValueError('USER/PASS ausentes no Server do config.json')
    return host, port, user, password, ssl_port
