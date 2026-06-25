import sqlite3, os
from agent.config import DB_PATH
SCHEMA = """
CREATE TABLE IF NOT EXISTS companies(ticker TEXT PRIMARY KEY, cik TEXT, name TEXT, added_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS filings(accession TEXT PRIMARY KEY, ticker TEXT, form TEXT, filed_date TEXT, url TEXT, processed INTEGER DEFAULT 0, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS trials(nct TEXT PRIMARY KEY, ticker TEXT, phase TEXT, status TEXT, primary_completion_date TEXT, last_status TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS insider_buys(id INTEGER PRIMARY KEY AUTOINCREMENT, accession TEXT, ticker TEXT, owner TEXT, txn_date TEXT, value REAL, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(accession, owner, txn_date, value));
CREATE TABLE IF NOT EXISTS fundamentals(ticker TEXT, period_end TEXT, cash REAL, quarterly_burn REAL, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(ticker, period_end));
CREATE TABLE IF NOT EXISTS catalysts(id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, ctype TEXT, cdate TEXT, label TEXT, source TEXT, ref TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(ticker, ctype, cdate, label));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, event_type TEXT, event_date TEXT, ref TEXT, summary TEXT, sentiment TEXT, detected_at TEXT DEFAULT CURRENT_TIMESTAMP, memo_status TEXT DEFAULT 'pending', UNIQUE(ticker, event_type, event_date, ref));
CREATE TABLE IF NOT EXISTS memos(event_id INTEGER PRIMARY KEY, ticker TEXT, memo_text TEXT, generator TEXT, generated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ingest_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, run_at TEXT DEFAULT CURRENT_TIMESTAMP, n_new INTEGER);
"""
def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH); con.execute("PRAGMA journal_mode=WAL"); return con
def init_db():
    con = connect(); con.executescript(SCHEMA); con.commit(); con.close()
def seed_companies():
    import json, urllib.request
    from agent.config import UNIVERSE, SEC_UA
    req = urllib.request.Request("https://www.sec.gov/files/company_tickers.json", headers={"User-Agent": SEC_UA})
    data = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
    tm = {r["ticker"].upper(): (str(r["cik_str"]).zfill(10), r["title"]) for r in data.values()}
    con = connect(); n=0; miss=[]
    for tk in UNIVERSE:
        if tk in tm:
            cik,name = tm[tk]; con.execute("INSERT OR REPLACE INTO companies(ticker,cik,name) VALUES(?,?,?)",(tk,cik,name)); n+=1
        else: miss.append(tk)
    con.commit(); con.close(); return n, miss
