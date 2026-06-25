import json, time, urllib.request, urllib.parse, re
import datetime as dt
from agent.config import SEC_UA
from agent.db.database import connect

CT="https://clinicaltrials.gov/api/v2/studies"
def gj(u): return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":SEC_UA}),timeout=40).read().decode("utf-8"))
def norm(s): return re.sub(r"[^a-z0-9 ]","",(s or "").lower()).strip()
def pdate(s):
    if not s: return None
    for f in ("%Y-%m-%d","%Y-%m","%Y"):
        try: return dt.datetime.strptime(s,f).date().isoformat()
        except ValueError: pass
    return None

def trials_for(name):
    out,token=[],None
    for _ in range(8):
        p={"query.spons":name,"pageSize":1000,"format":"json"}
        if token: p["pageToken"]=token
        try: j=gj(CT+"?"+urllib.parse.urlencode(p))
        except Exception: break
        out+=j.get("studies",[]); token=j.get("nextPageToken")
        if not token: break
        time.sleep(0.2)
    return out

def upsert_trial(con, tk, nct, phase, status, pcd):
    row=con.execute("SELECT status FROM trials WHERE nct=?",(nct,)).fetchone()
    if row is None:
        con.execute("INSERT INTO trials(nct,ticker,phase,status,primary_completion_date,last_status) VALUES(?,?,?,?,?,?)",
                    (nct,tk,phase,status,pcd,status)); return None
    old=row[0]
    if old!=status:
        con.execute("UPDATE trials SET status=?,last_status=?,phase=?,primary_completion_date=?,updated_at=CURRENT_TIMESTAMP WHERE nct=?",
                    (status,old,phase,pcd,nct))
        return (tk,nct,old,status)
    con.execute("UPDATE trials SET phase=?,primary_completion_date=?,updated_at=CURRENT_TIMESTAMP WHERE nct=?",(phase,pcd,nct))
    return None

def ingest(verbose=True):
    con=connect(); companies=con.execute("SELECT ticker,name FROM companies").fetchall()
    total_new=0; total_chg=[]
    for tk,name in companies:
        tok=norm(name).split()[0] if norm(name) else tk.lower()
        before=con.execute("SELECT COUNT(*) FROM trials WHERE ticker=?",(tk,)).fetchone()[0]
        n=0
        for st in trials_for(name):
            ps=st.get("protocolSection",{})
            lead=norm(ps.get("sponsorCollaboratorsModule",{}).get("leadSponsor",{}).get("name"))
            if tok not in lead: continue
            idm=ps.get("identificationModule",{}); sm=ps.get("statusModule",{}); dm=ps.get("designModule",{})
            nct=idm.get("nctId"); 
            if not nct: continue
            phase=",".join(dm.get("phases",[]) or [])
            status=sm.get("overallStatus","")
            pcd=pdate(sm.get("primaryCompletionDateStruct",{}).get("date"))
            chg=upsert_trial(con,tk,nct,phase,status,pcd)
            if chg: total_chg.append(chg)
            n+=1
        con.commit()
        after=con.execute("SELECT COUNT(*) FROM trials WHERE ticker=?",(tk,)).fetchone()[0]
        new=after-before; total_new+=new
        if verbose: print(f"  {tk:5}: {n} ensaios ({new} novos)")
        time.sleep(0.2)
    con.execute("INSERT INTO ingest_runs(source,n_new) VALUES('trials',?)",(total_new,)); con.commit()
    if total_chg:
        print("\n  >>> MUDANCAS DE ESTADO DETETADAS:")
        for tk,nct,old,new in total_chg: print(f"      {tk} {nct}: {old} -> {new}")
    con.close(); return total_new, total_chg
