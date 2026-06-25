import json, time, urllib.request
from agent.config import SEC_UA
from agent.db.database import connect

DILUTION_FORMS={"424B1","424B2","424B3","424B4","424B5","424B7","424B8"}  # prospetos de oferta (diluicao efetiva)
def gj(u):
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":SEC_UA}),timeout=40).read().decode("utf-8"))
    except Exception: return None

def dilution_filings(cik):
    base=gj(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if not base: return []
    blocks=[base["filings"]["recent"]]
    for f in base["filings"].get("files",[]):
        b=gj(f"https://data.sec.gov/submissions/{f['name']}")
        if b: blocks.append(b)
        time.sleep(0.1)
    out=[]
    for b in blocks:
        F,D,A=b.get("form",[]),b.get("filingDate",[]),b.get("accessionNumber",[])
        for i in range(len(F)):
            if F[i] in DILUTION_FORMS and D[i]>="2018-01-01": out.append((A[i],D[i],F[i]))
    return out

def ingest(verbose=True):
    con=connect(); companies=con.execute("SELECT ticker,cik FROM companies").fetchall(); total=0
    for tk,cik in companies:
        if not cik: continue
        ci=str(int(cik)); new=0
        for acc,fd,form in dilution_filings(cik):
            nod=acc.replace("-",""); url=f"https://www.sec.gov/Archives/edgar/data/{ci}/{nod}/{acc}.txt"
            cur=con.execute("INSERT OR IGNORE INTO dilutions(accession,ticker,form,filed_date,url) VALUES(?,?,?,?,?)",(acc,tk,form,fd,url))
            new+=cur.rowcount
        con.commit(); total+=new
        if verbose and new: print(f"  {tk:5}: +{new} ofertas (424B)")
        time.sleep(0.12)
    con.execute("INSERT INTO ingest_runs(source,n_new) VALUES('dilutions',?)",(total,)); con.commit(); con.close()
    return total

def show_alerts(months=12):
    import datetime as dt
    con=connect(); cutoff=(dt.date.today()-dt.timedelta(days=months*30)).isoformat()
    rows=con.execute("""
      SELECT d.ticker,d.filed_date,d.form,f.runway_quarters,f.stale
      FROM dilutions d LEFT JOIN fundamentals f ON d.ticker=f.ticker
      WHERE d.filed_date>=? ORDER BY d.filed_date DESC
    """,(cutoff,)).fetchall()
    print(f"\n=== OFERTAS DE ACOES (424B) ultimos {months} meses ===")
    if not rows: print("  (nenhuma)"); con.close(); return
    for tk,fd,form,rw,stale in rows:
        if rw is not None and not stale and rw<6: alerta=f"  <-- ALERTA: diluiu com runway CURTO ({rw:.0f}T)"
        elif rw is not None and not stale: alerta=f"  (runway {rw:.0f}T)"
        else: alerta=""
        print(f"  {fd} | {tk:5} | {form}{alerta}")
    con.close()
