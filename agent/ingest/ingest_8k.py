import json, time, urllib.request
from agent.config import SEC_UA
from agent.db.database import connect
def gj(u):
    req = urllib.request.Request(u, headers={"User-Agent": SEC_UA})
    return json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
def recent_8ks(cik):
    base = gj(f"https://data.sec.gov/submissions/CIK{cik}.json")
    blocks = [base["filings"]["recent"]]
    for f in base["filings"].get("files", []):
        try: blocks.append(gj(f"https://data.sec.gov/submissions/{f[chr(39)+'name'+chr(39)]}")); time.sleep(0.12)
        except Exception: pass
    out=[]
    for b in blocks:
        F,D,A = b.get("form",[]),b.get("filingDate",[]),b.get("accessionNumber",[])
        for i in range(len(F)):
            if F[i]=="8-K" and D[i]>="2018-01-01": out.append((A[i], D[i]))
    return out
def store_filings(con, tk, ci, filings):
    new=0
    for acc, fd in filings:
        nod=acc.replace("-",""); url=f"https://www.sec.gov/Archives/edgar/data/{ci}/{nod}/{acc}.txt"
        cur=con.execute("INSERT OR IGNORE INTO filings(accession,ticker,form,filed_date,url) VALUES(?,?,?,?,?)",(acc,tk,"8-K",fd,url))
        new+=cur.rowcount
    return new
def ingest(verbose=True):
    con=connect(); companies=con.execute("SELECT ticker,cik FROM companies").fetchall(); total=0
    for tk,cik in companies:
        if not cik: continue
        ci=str(int(cik))
        try: filings=recent_8ks(cik)
        except Exception as e:
            if verbose: print(f"  ! {tk}: erro {e}")
            continue
        new=store_filings(con,tk,ci,filings); con.commit(); total+=new
        if verbose: print(f"  {tk:5}: {len(filings)} vistos, {new} novos")
        time.sleep(0.1)
    con.execute("INSERT INTO ingest_runs(source,n_new) VALUES('8-K',?)",(total,)); con.commit(); con.close()
    return total
