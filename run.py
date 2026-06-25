from agent.envload import load_env
load_env()
import sys
from agent.db.database import init_db, seed_companies, connect
def cmd_init():
    init_db(); print("DB inicializada."); n,miss=seed_companies(); print(f"Universo: {n} com CIK." + (f" Sem CIK: {miss}" if miss else ""))
def cmd_ingest_8k():
    from agent.ingest.ingest_8k import ingest; print("8-K..."); print(f"novos: {ingest()}")
def cmd_ingest_trials():
    from agent.ingest.ingest_trials import ingest; print("ensaios..."); n,chg=ingest(); print(f"novos: {n} | mudancas: {len(chg)}")
def cmd_ingest_prices():
    from agent.ingest.ingest_prices import ingest; print("precos..."); print(f"ok: {ingest()}")
def cmd_ingest_fundamentals():
    from agent.ingest.ingest_fundamentals import ingest; print("runway..."); print(f"ok: {ingest()}")
def cmd_ingest_insiders():
    from agent.ingest.ingest_insiders import ingest; print("insiders (resumivel)..."); print(f"compras: {ingest()}")
def cmd_ingest_dilution():
    from agent.ingest.ingest_dilution import ingest, show_alerts; print("diluicao..."); print(f"ofertas: {ingest()}"); show_alerts()
def cmd_dilution_alerts():
    from agent.ingest.ingest_dilution import show_alerts; show_alerts()
def cmd_detect_8k():
    from agent.detect.detect_8k import process
    lim=int(sys.argv[2]) if len(sys.argv)>2 else None
    print("processar 8-K..."); d,c,p=process(limit=lim); print(f"processados: {d} | eventos: {c} | PDUFA: {p}")
def cmd_calendar():
    from agent.report.calendar import rebuild_calendar, show_calendar; rebuild_calendar(); show_calendar()
def cmd_profile():
    from agent.report.onepager import one_pager, all_companies
    con=connect()
    if len(sys.argv)>2: print(one_pager(con, sys.argv[2].upper()))
    else:
        for tk in all_companies(con): print(one_pager(con,tk)); print()
    con.close()
def cmd_memos():
    from agent.report.memo import generate
    gen="auto"; lim=None
    for a in sys.argv[2:]:
        if a in ("template","groq","auto"): gen=a
        elif a.isdigit(): lim=int(a)
    print("A gerar memos..."); n=generate(generator=gen,limit=lim); print(f"\nMemos gerados: {n}")
def cmd_show_memos():
    from agent.report.memo import show
    tk=sys.argv[2] if len(sys.argv)>2 and not sys.argv[2].isdigit() else None
    show(ticker=tk)
def cmd_status():
    con=connect(); print("=== ESTADO DA BASE DE DADOS ===")
    for t in ["companies","filings","trials","insider_buys","fundamentals","prices","dilutions","catalysts","events","memos"]:
        try: c=con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception: c="-"
        print(f"  {t:16}: {c}")
    pend=con.execute("SELECT COUNT(*) FROM events WHERE memo_status!='done'").fetchone()[0]; print(f"  (eventos sem memo: {pend})")
    for s,r,n in con.execute("SELECT source,run_at,n_new FROM ingest_runs ORDER BY id DESC LIMIT 8").fetchall(): print(f"  {r} | {s} | +{n}")
    con.close()
def cmd_update():
    from agent.update import update_all
    skip = "--skip-insiders" in sys.argv or "fast" in sys.argv[2:]
    update_all(skip_heavy=skip)
def cmd_site():
    from agent.report.site import build
    p=build(); print(f"Abre: {p}")
CMDS={"init":cmd_init,"ingest-8k":cmd_ingest_8k,"ingest-trials":cmd_ingest_trials,"ingest-prices":cmd_ingest_prices,"ingest-fundamentals":cmd_ingest_fundamentals,"ingest-insiders":cmd_ingest_insiders,"ingest-dilution":cmd_ingest_dilution,"dilution-alerts":cmd_dilution_alerts,"detect-8k":cmd_detect_8k,"calendar":cmd_calendar,"profile":cmd_profile,"memos":cmd_memos,"show-memos":cmd_show_memos,"update":cmd_update,"site":cmd_site,"status":cmd_status}
if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "status"
    (CMDS.get(cmd) or (lambda: print(f"Comandos: {chr(44).join(CMDS)}")))()


