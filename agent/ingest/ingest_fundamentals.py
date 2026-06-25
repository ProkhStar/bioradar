import json, time, urllib.request
import datetime as dt
from agent.config import SEC_UA
from agent.db.database import connect

TODAY=dt.date.today()
def gj(u):
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":SEC_UA}),timeout=40).read().decode("utf-8"))
    except Exception: return None
def concept(cik, tag, taxonomy="us-gaap"):
    j=gj(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json")
    if not j: return []
    out=[]
    for unit,facts in j.get("units",{}).items(): out+=facts
    return out
def best(cik, tags):
    for t in tags:
        u=concept(cik,t)
        if u: return u
    return []

def instant_by_date(units):
    d={}
    for u in units:
        if "start" not in u and u.get("end") and u.get("val") is not None: d[u["end"]]=float(u["val"])
    return d
def quarterly_flows(units):
    out=[]
    for u in units:
        s,e,v=u.get("start"),u.get("end"),u.get("val")
        if s and e and v is not None:
            try: dd=(dt.date.fromisoformat(e)-dt.date.fromisoformat(s)).days
            except Exception: continue
            if 80<=dd<=100: out.append((e,float(v)))
    out.sort(); return out

CASH_TAGS=["CashAndCashEquivalentsAtCarryingValue","CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]
STI_TAGS=["ShortTermInvestments","MarketableSecuritiesCurrent","AvailableForSaleSecuritiesCurrent","ShortTermInvestmentsTotal"]
FLOW_TAGS=["NetCashProvidedByUsedInOperatingActivities","NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]

def total_liquidity(cik, max_age_days=275):
    cash=instant_by_date(best(cik,CASH_TAGS))
    if not cash: return None
    sti=instant_by_date(best(cik,STI_TAGS))
    end=max(cash)                                  # data mais recente com caixa
    total=cash.get(end,0)+sti.get(end,0)           # + investimentos CP na mesma data
    age=(TODAY-dt.date.fromisoformat(end)).days
    return end, total, age>max_age_days

def ingest(verbose=True):
    con=connect(); companies=con.execute("SELECT ticker,cik FROM companies").fetchall(); n=0
    for tk,cik in companies:
        if not cik: continue
        liq=total_liquidity(cik); flows=quarterly_flows(best(cik,FLOW_TAGS))
        if not liq:
            if verbose: print(f"  {tk:5}: sem dados de caixa"); 
            time.sleep(0.15); continue
        period_end, cash_val, stale = liq
        burn=None; runway=None
        if flows:
            recent=[v for (e,v) in flows[-4:]]; avg_q=sum(recent)/len(recent)
            if avg_q<0: burn=-avg_q; runway=cash_val/burn
        con.execute("INSERT OR REPLACE INTO fundamentals(ticker,period_end,cash,quarterly_burn,runway_quarters,stale) VALUES(?,?,?,?,?,?)",
                    (tk,period_end,cash_val,burn,runway,1 if stale else 0))
        n+=1
        if verbose:
            flag=" [DESATUALIZADO]" if stale else ""
            if runway and not stale: print(f"  {tk:5}: liquidez ${cash_val/1e6:6.0f}M | queima/T ${burn/1e6:5.1f}M | runway {runway:4.1f}T (~{runway*3:2.0f}m) [{period_end}]")
            elif stale: print(f"  {tk:5}: ${cash_val/1e6:6.0f}M [{period_end}]{flag} -> ignorar runway")
            else: print(f"  {tk:5}: liquidez ${cash_val/1e6:6.0f}M | sem queima (fluxo positivo) [{period_end}]")
        time.sleep(0.2)
    con.commit(); con.execute("INSERT INTO ingest_runs(source,n_new) VALUES('fundamentals',?)",(n,)); con.commit(); con.close()
    return n
