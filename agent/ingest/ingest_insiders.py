import json, time, urllib.request, re
from agent.config import SEC_UA
from agent.db.database import connect

def gj(u):
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":SEC_UA}),timeout=40).read().decode("utf-8"))
    except Exception: return None
def gt(u):
    try: return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":SEC_UA}),timeout=40).read().decode("utf-8","replace")
    except Exception: return None

def form4_list(cik):
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
            if F[i]=="4" and D[i]>="2018-01-01": out.append((A[i],D[i]))
    return out

def form4_xml(cik_int, acc):
    nod=acc.replace("-","")
    idx=gj(f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{nod}/index.json")
    if not idx: return None
    name=None
    for it in idx.get("directory",{}).get("item",[]):
        n=it.get("name","")
        if n.endswith(".xml") and not n.startswith("xslF"):  # XML cru, nao a versao renderizada
            name=n; break
    if not name: return None
    return gt(f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{nod}/{name}")

def parse_buys(xml, acc, tk):
    if not xml: return []
    owner_m=re.search(r"<rptOwnerName>([^<]+)</rptOwnerName>", xml)
    owner=owner_m.group(1).strip() if owner_m else "?"
    buys=[]
    for tx in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", xml, re.S):
        code_m=re.search(r"<transactionCode>([^<]+)</transactionCode>", tx)
        if not code_m or code_m.group(1).strip()!="P": continue
        date_m=re.search(r"<transactionDate>\s*<value>([^<]+)</value>", tx)
        shares_m=re.search(r"<transactionShares>\s*<value>([^<]+)</value>", tx)
        price_m=re.search(r"<transactionPricePerShare>\s*<value>([^<]*)</value>", tx)
        date=date_m.group(1) if date_m else None
        shares=float(shares_m.group(1)) if shares_m and shares_m.group(1) else 0
        price=float(price_m.group(1)) if price_m and price_m.group(1) else 0
        buys.append((acc,tk,owner,date,shares*price))
    return buys

def done_companies(con):
    return set(r[0] for r in con.execute("SELECT DISTINCT ticker FROM insider_buys").fetchall())

def ingest(verbose=True):
    con=connect(); companies=con.execute("SELECT ticker,cik FROM companies").fetchall()
    dn=done_companies(con); print(f"resumir: {len(dn)} empresas ja com insiders")
    total=0
    for tk,cik in companies:
        if not cik or tk in dn: continue
        ci=str(int(cik)); lst=form4_list(cik); nb=0
        for acc,fd in lst:
            xml=form4_xml(ci,acc); time.sleep(0.1)
            for b in parse_buys(xml,acc,tk):
                cur=con.execute("INSERT OR IGNORE INTO insider_buys(accession,ticker,owner,txn_date,value) VALUES(?,?,?,?,?)",b)
                nb+=cur.rowcount
        con.commit(); total+=nb
        if verbose: print(f"  ok {tk:5}: {len(lst)} Form 4 -> {nb} compras")
        time.sleep(0.1)
    con.execute("INSERT INTO ingest_runs(source,n_new) VALUES('insiders',?)",(total,)); con.commit(); con.close()
    return total
