import urllib.request, re, html, time
from agent.config import SEC_UA
from agent.db.database import connect

def gt(u): return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":SEC_UA}),timeout=45).read().decode("utf-8","replace")

def is_material(raw):
    descs=" ".join(re.findall(r"ITEM INFORMATION:\s*([^\n]+)", raw)).lower()
    return ("other events" in descs) or ("regulation fd" in descs)

def strong_signals(t):
    t=t.lower(); sig=[]
    if re.search(r"(top-?line|primary endpoint|primary efficacy|co-primary|met (its|the) primary|did not meet|failed to meet|achieved (its|the) primary)", t) and re.search(r"(phase|trial|study|patients)", t): sig.append("readout")
    if (re.search(r"\bpdufa\b",t) or "complete response letter" in t or "target action date" in t
        or re.search(r"(received|granted|announced|reported) .{0,40}(fda approval|approval (from|by) the fda|marketing authorization)",t)
        or re.search(r"fda (approved|accepted|granted|issued)",t)
        or re.search(r"(approval|acceptance) of (its|the|a) (nda|bla|snda|sbla)",t) or "advisory committee" in t): sig.append("regulatory")
    if re.search(r"(breakthrough therapy designation|fast track designation|orphan drug designation|priority review|regenerative medicine advanced therapy|rare pediatric disease designation)",t): sig.append("designation")
    return sig

def sentiment(t):
    t=t.lower()
    pos=any(k in t for k in ["met its primary","met the primary","achieved its primary","achieved the primary","statistically significant","positive topline","positive top-line","fda approved","received fda approval","breakthrough therapy designation","priority review","granted"])
    neg=any(k in t for k in ["did not meet","failed to meet","complete response letter","discontinu","terminat","missed the primary"])
    return "pos" if (pos and not neg) else ("neg" if (neg and not pos) else ("misto" if pos and neg else "neutro"))

MONTHS="January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE=re.compile(rf"({MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})",re.I)
MNUM={m.lower():i+1 for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"])}
def extract_pdufa(t):
    low=t.lower()
    for kw in ["pdufa","target action date","action date of","goal date"]:
        i=low.find(kw)
        if i>=0:
            m=DATE_RE.search(t[i:i+160])
            if m: return f"{int(m.group(3)):04d}-{MNUM[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    return None

def process(limit=None, verbose=True):
    con=connect()
    q="SELECT accession,ticker,filed_date,url FROM filings WHERE form='8-K' AND processed=0 ORDER BY filed_date"
    if limit: q+=f" LIMIT {int(limit)}"
    todo=con.execute(q).fetchall()
    print(f"8-K por processar: {len(todo)}")
    n_cat=0; n_pdufa=0; n_done=0
    for acc,tk,fd,url in todo:
        try: raw=gt(url)
        except Exception as e:
            con.execute("UPDATE filings SET processed=1 WHERE accession=?",(acc,)); con.commit()  # marca p/ nao repetir
            continue
        con.execute("UPDATE filings SET processed=1 WHERE accession=?",(acc,))
        if is_material(raw):
            body=re.sub(r"(?s)<[^>]+>"," ",raw); body=re.sub(r"\s+"," ",html.unescape(body))[:200000]
            sig=strong_signals(body)
            if sig:
                etype="regulatory" if "regulatory" in sig else ("readout" if "readout" in sig else "designation")
                con.execute("INSERT OR IGNORE INTO events(ticker,event_type,event_date,ref,summary,sentiment) VALUES(?,?,?,?,?,?)",
                            (tk,etype,fd,acc,";".join(sig),sentiment(body))); n_cat+=1
                pdufa=extract_pdufa(body)
                if pdufa:
                    con.execute("INSERT OR IGNORE INTO catalysts(ticker,ctype,cdate,label,source,ref) VALUES(?,?,?,?,?,?)",
                                (tk,"pdufa",pdufa,"Decisao FDA (PDUFA)","8-K",acc)); n_pdufa+=1
        n_done+=1
        if n_done%200==0:
            con.commit()
            if verbose: print(f"  ... {n_done}/{len(todo)} processados, {n_cat} eventos, {n_pdufa} PDUFA")
        time.sleep(0.1)
    con.commit()
    con.execute("INSERT INTO ingest_runs(source,n_new) VALUES('8-K-detect',?)",(n_cat,)); con.commit()
    con.close()
    return n_done, n_cat, n_pdufa
