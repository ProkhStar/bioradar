import datetime as dt
from agent.db.database import connect

def one_pager(con, tk):
    row=con.execute("SELECT name FROM companies WHERE ticker=?",(tk,)).fetchone()
    if not row: return f"(empresa {tk} nao encontrada)"
    name=row[0]
    L=["="*64, f"  {tk} — {name}", "="*64]
    p=con.execute("SELECT price,chg_1d,chg_30d,mktcap,asof FROM prices WHERE ticker=?",(tk,)).fetchone()
    if p and p[0]:
        mc=f"${p[3]/1e9:.1f}B" if p[3] else "n/d"
        c1=f"{p[1]:+.1%}" if p[1] is not None else "n/d"; c30=f"{p[2]:+.1%}" if p[2] is not None else "n/d"
        L.append(f"PRECO: ${p[0]:.2f} | 1d {c1} | 30d {c30} | mktcap {mc} [{p[4]}]")
    f=con.execute("SELECT cash,quarterly_burn,runway_quarters,stale,period_end FROM fundamentals WHERE ticker=?",(tk,)).fetchone()
    if f:
        if f[3]: L.append(f"CAIXA: ${f[0]/1e6:.0f}M [DESATUALIZADO {f[4]}] -> runway nao fiavel")
        elif f[2]:
            rwm="(+60m)" if f[2]>20 else f"(~{f[2]*3:.0f}m)"
            alert=" *** RUNWAY CURTO ***" if f[2]<6 else ""
            L.append(f"CASH RUNWAY: ${f[0]/1e6:.0f}M / ${f[1]/1e6:.1f}M por T = {f[2]:.1f}T {rwm}{alert}")
        else: L.append(f"CAIXA: ${f[0]/1e6:.0f}M (fluxo operacional positivo, sem queima)")
    today=dt.date.today().isoformat()
    cats=con.execute("SELECT cdate,ctype,label FROM catalysts WHERE ticker=? AND cdate>=? ORDER BY cdate LIMIT 5",(tk,today)).fetchall()
    if cats:
        L.append("PROXIMOS CATALISADORES:")
        for cd,ct,lab in cats:
            d=(dt.date.fromisoformat(cd)-dt.date.today()).days
            L.append(f"   {cd} (+{d:>3}d) | {ct:8} | {lab}")
    ph=con.execute("SELECT phase,COUNT(*) FROM trials WHERE ticker=? AND status NOT IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED') GROUP BY phase ORDER BY phase DESC",(tk,)).fetchall()
    if ph: L.append("PIPELINE (ensaios ativos): "+", ".join(f"{p or '?'}: {c}" for p,c in ph if p))
    ins=con.execute("SELECT COUNT(*),SUM(value),MAX(txn_date) FROM insider_buys WHERE ticker=? AND txn_date>=date('now','-365 days')",(tk,)).fetchone()
    if ins and ins[0]:
        tot=ins[1] or 0
        L.append(f"INSIDERS (12m): {ins[0]} compras, total ${tot/1e6:.1f}M (ultima {ins[2]})")
    dil=con.execute("SELECT COUNT(*),MAX(filed_date) FROM dilutions WHERE ticker=? AND filed_date>=date('now','-365 days')",(tk,)).fetchone()
    if dil and dil[0]:
        rw=f[2] if (f and f[2] and not f[3]) else None
        flag=" (com runway curto!)" if (rw is not None and rw<6) else ""
        L.append(f"DILUICAO (12m): {dil[0]} ofertas 424B (ultima {dil[1]}){flag}")
    evs=con.execute("SELECT event_date,event_type,sentiment FROM events WHERE ticker=? ORDER BY event_date DESC LIMIT 4",(tk,)).fetchall()
    if evs:
        L.append("EVENTOS RECENTES (8-K):")
        for ed,et,se in evs: L.append(f"   {ed} | {et:11} | {se}")
    return "\n".join(L)

def all_companies(con):
    return [r[0] for r in con.execute("SELECT ticker FROM companies ORDER BY ticker").fetchall()]
