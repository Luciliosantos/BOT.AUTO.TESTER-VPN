#!/bin/bash
set -e

APP_DIR="/opt/BOT.AUTO.TESTER-VPN"
REPO_URL="https://github.com/Luciliosantos/BOT.AUTO.TESTER-VPN.git"

echo
echo "======================================"
echo "       BOT AUTO TESTER VPN"
echo "======================================"
echo

if [ "$EUID" -ne 0 ]; then
    echo "ERRO: execute como root."
    exit 1
fi

read -rp "Token do BOT Telegram: " BOT_TOKEN
echo
read -rp "ID Telegram do administrador: " ADMIN_ID
echo

if [ -z "$BOT_TOKEN" ]; then
    echo "ERRO: BOT_TOKEN não pode ficar vazio."
    exit 1
fi

if ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
    echo "ERRO: o ID Telegram deve conter apenas números."
    exit 1
fi

echo
echo "[1/6] Instalando dependências do sistema..."

apt-get update -y
apt-get install -y git python3 python3-venv python3-pip

echo
echo "[2/6] Preparando aplicação..."

if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR"
    git fetch origin
    git reset --hard origin/main
else
    rm -rf "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

echo
echo "[3/6] Criando ambiente Python..."

python3 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "[4/6] Criando configuração..."

mkdir -p data results

cat > .env <<ENV
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_ID
CONFIG_PATH=data/config.json
TEST_TIMEOUT=12
CONCURRENCY=8
ENV

chmod 600 .env

echo
echo "[5/6] Verificando código"
