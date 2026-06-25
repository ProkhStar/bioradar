import datetime as dt
from agent.db.database import connect

INACTIVE=("COMPLETED","TERMINATED","WITHDRAWN","SUSPENDED")

def rebuild_calendar(verbose=True):
    con=connect(); today=dt.date.today().isoformat()
    con.execute("DELETE FROM catalysts WHERE source=?",("CT.gov",))
    rows=con.execute(
        "SELECT ticker,nct,phase,status,primary_completion_date FROM trials "
        "WHERE primary_completion_date >= ? AND status NOT IN (?,?,?,?) "
        "ORDER BY primary_completion_date",
        (today,*INACTIVE)).fetchall()
    for tk,nct,phase,status,pcd in rows:
        label=f"Readout {phase or 'ensaio'} ({status})"
        con.execute("INSERT OR IGNORE INTO catalysts(ticker,ctype,cdate,label,source,ref) VALUES(?,?,?,?,?,?)",
                    (tk,"readout",pcd,label,"CT.gov",nct))
    con.commit()
    n=con.execute("SELECT COUNT(*) FROM catalysts WHERE source=?",("CT.gov",)).fetchone()[0]
    con.close(); return n

def show_calendar(days=365, limit=40):
    con=connect(); today=dt.date.today(); horizon=(today+dt.timedelta(days=days)).isoformat()
    rows=con.execute(
        "SELECT cdate,ticker,ctype,label,ref FROM catalysts WHERE cdate>=? AND cdate<=? ORDER BY cdate LIMIT ?",
        (today.isoformat(),horizon,limit)).fetchall()
    total=con.execute("SELECT COUNT(*) FROM catalysts").fetchone()[0]
    print(f"\n=== CALENDARIO DE CATALISADORES (proximos {days} dias) ===")
    if not rows:
        print("  (vazio)"); con.close(); return
    for cdate,tk,ct,label,ref in rows:
        d=(dt.date.fromisoformat(cdate)-today).days
        print(f"  {cdate} (+{d:>3}d) | {tk:5} | {ct:10} | {label} | {ref}")
    print(f"\n  a mostrar {len(rows)} de {total} catalisadores no calendario")
    con.close()
