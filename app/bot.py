from __future__ import annotations
import asyncio, json, os, re
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from .config import load_config
from .models import Target
from .tester import run_batch

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; RESULTS=ROOT/'results'; DATA.mkdir(exist_ok=True); RESULTS.mkdir(exist_ok=True)
CONFIG=Path(os.getenv('CONFIG_PATH', DATA/'config.json'))
TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMINS={int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
TIMEOUT=float(os.getenv('TEST_TIMEOUT','12')); CONCURRENCY=int(os.getenv('CONCURRENCY','8'))
SESSIONS={}; RUNNING={}

def allowed(uid): return uid in ADMINS

def parse_targets(text):
    ips=[]; snis=[]; section=None
    for raw in text.splitlines():
        line=raw.strip()
        if not line: continue
        head=line.upper().rstrip(':')
        if head in ('IP','IPS','IP/PROXY','PROXY','PROXIES'):
            section='ip'; continue
        if head in ('SNI','SNIS','DOMINIO','DOMINIOS','DOMAINS'):
            section='sni'; continue
        line=re.sub(r'^[•\-*\d\.)\s]+','',line).strip()
        if not line: continue
        host=line.split('://',1)[-1].split('/',1)[0]
        if host.count(':')==1: host=host.rsplit(':',1)[0]
        import ipaddress
        try:
            ipaddress.ip_address(host); ips.append(host); continue
        except ValueError: pass
        if section=='ip': ips.append(host)
        elif section=='sni' or re.match(r'^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$',host): snis.append(host)
    return [Target('ip',x) for x in dict.fromkeys(ips)] + [Target('sni',x) for x in dict.fromkeys(snis)]

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if not allowed(update.effective_user.id): return
    await update.message.reply_text('🤖 AUTO TESTER VPN\n\n/config → envie o config.json\nDepois envie IPs e SNI/domínios.\n/test → inicia todos os testes.\n/status → situação.\n/cancel → cancela.')

async def config_doc(update, context):
    if not allowed(update.effective_user.id): return
    doc=update.message.document
    if not doc or not doc.file_name.lower().endswith('.json'):
        await update.message.reply_text('Envie o config.json como documento.')
        return
    f=await doc.get_file(); await f.download_to_drive(str(CONFIG))
    try:
        cfg=load_config(CONFIG)
        await update.message.reply_text(f'✅ Config cadastrado. Servers: {len(cfg["Servers"])} | Networks: {len(cfg["Networks"])}')
    except Exception as e:
        await update.message.reply_text(f'❌ Config inválido: {e}')

async def receive_targets(update, context):
    if not allowed(update.effective_user.id): return
    targets=parse_targets(update.message.text or '')
    if not targets:
        await update.message.reply_text('Não encontrei IP ou domínio. Use IP: e SNI: para deixar explícito.')
        return
    SESSIONS[update.effective_user.id]=targets
    await update.message.reply_text(f'📥 Recebidos {sum(x.kind=="ip" for x in targets)} IP(s) e {sum(x.kind=="sni" for x in targets)} domínio(s). Use /test.')

async def status(update, context):
    if not allowed(update.effective_user.id): return
    ts=SESSIONS.get(update.effective_user.id,[])
    try: cfg=load_config(CONFIG); c=f'OK ({len(cfg["Servers"])} servidores / {len(cfg["Networks"])} redes)'
    except Exception as e: c=f'ERRO: {e}'
    await update.message.reply_text(f'Config: {c}\nAlvos: {len(ts)}\nTeste: {"rodando" if update.effective_user.id in RUNNING else "parado"}')

async def cancel(update, context):
    if not allowed(update.effective_user.id): return
    t=RUNNING.pop(update.effective_user.id,None)
    if t: t.cancel(); await update.message.reply_text('🛑 Cancelado.')

async def test(update, context):
    uid=update.effective_user.id
    if not allowed(uid): return
    if uid in RUNNING: await update.message.reply_text('Já existe um teste rodando.'); return
    try: cfg=load_config(CONFIG)
    except Exception as e: await update.message.reply_text(f'❌ {e}'); return
    targets=SESSIONS.get(uid,[])
    if not targets: await update.message.reply_text('Envie primeiro os IPs/domínios.'); return
    total=len(targets)*len(cfg['Servers'])*len(cfg['Networks'])
    await update.message.reply_text(f'🚀 Iniciando {total} testes...')
    async def on_result(r):
        if r.status=='ok':
            await update.message.reply_text(f'✅ {r.kind.upper()} FUNCIONOU\n{r.target}\nConfig: {r.network} | {r.elapsed_ms} ms')
    task=asyncio.create_task(run_batch(cfg,targets,TIMEOUT,CONCURRENCY,on_result)); RUNNING[uid]=task
    try:
        results=await task
        out=[r.to_dict() for r in results]
        (RESULTS/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
        good=[r.config for r in results if r.status=='ok' and r.config]
        # preserva Servers e somente Networks aprovadas
        seen=set(); nets=[]
        for n in good:
            key=json.dumps(n,sort_keys=True,ensure_ascii=False)
            if key not in seen: seen.add(key); nets.append(n)
        final={'Version':cfg.get('Version',0),'Servers':cfg['Servers'],'Networks':nets}
        (RESULTS/'config_funcionais.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
        counts={}
        for r in results: counts[r.status]=counts.get(r.status,0)+1
        await update.message.reply_text(f'🏁 FINALIZADO\nTotal: {len(results)}\n✅ OK: {counts.get("ok",0)}\n⏱️ Timeout: {counts.get("timeout",0)}\n🔐 Auth: {counts.get("auth_failed",0)}\n❌ Erros: {counts.get("error",0)}')
        await update.message.reply_document((RESULTS/'config_funcionais.json').open('rb'),caption='📦 Configurações funcionais')
    except asyncio.CancelledError:
        await update.message.reply_text('🛑 Teste cancelado.')
    finally: RUNNING.pop(uid,None)

def main():
    if not TOKEN: raise SystemExit('Defina BOT_TOKEN no .env')
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start',start)); app.add_handler(CommandHandler('config',config_doc)); app.add_handler(CommandHandler('test',test)); app.add_handler(CommandHandler('status',status)); app.add_handler(CommandHandler('cancel',cancel))
    app.add_handler(MessageHandler(filters.Document.ALL,config_doc)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,receive_targets))
    app.run_polling()
if __name__=='__main__': main()
