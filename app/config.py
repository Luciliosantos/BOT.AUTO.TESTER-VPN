from __future__ import annotations
import copy
import json
import os
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    path = Path(path)

    if not path.exists():
        raise ValueError("config.json ainda não foi cadastrado pelo bot")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido: {e}")

    if not isinstance(data, dict):
        raise ValueError("config.json deve ser um objeto JSON")

    data.setdefault("Servers", [])
    data.setdefault("Networks", [])

    if not data["Servers"]:
        raise ValueError("config.json não possui Servers")

    if not data["Networks"]:
        raise ValueError("config.json não possui Networks")

    return data


def save_credentials(path: str | Path, username: str, password: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "username": username.strip(),
        "password": password,
    }

    if not data["username"] or not data["password"]:
        raise ValueError("Usuário e senha não podem ficar vazios")

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_credentials(path: str | Path) -> tuple[str, str]:
    path = Path(path)

    if not path.exists():
        raise ValueError("Credenciais ainda não cadastradas")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Arquivo de credenciais inválido: {e}")

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        raise ValueError("Usuário ou senha não cadastrados")

    return username, password


def clone_for_target(
    network: dict[str, Any],
    target_kind: str,
    target: str,
) -> dict[str, Any]:
    c = copy.deepcopy(network)

    if target_kind == "ip":
        c["ProxyIP"] = target
        c["ProxyPort"] = "80"

    elif target_kind == "sni":
        c["SNI"] = target
        c["_test_tls_port"] = 443

    else:
        raise ValueError(f"Tipo de alvo inválido: {target_kind}")

    return c


def server_values(
    server: dict[str, Any],
    credentials_path: str | Path | None = None,
):
    host = str(
        server.get("ServerIP")
        or server.get("server_host")
        or ""
    ).strip()

    port = int(
        server.get("ServerPort")
        or server.get("server_port")
        or 22
    )

    user = str(
        server.get("USER")
        or server.get("username")
        or ""
    )

    password = str(
        server.get("PASS")
        or server.get("password")
        or ""
    )

    ssl_port = int(
        server.get("SSLPort")
        or server.get("ssl_port")
        or 443
    )

    if credentials_path and (not user or not password):
        user, password = load_credentials(credentials_path)

    if not host:
        raise ValueError("ServerIP vazio")

    if not user or not password:
        raise ValueError(
            "USER/PASS não encontrados no config.json "
            "nem nas credenciais cadastradas"
        )

    return host, port, user, password, ssl_port
