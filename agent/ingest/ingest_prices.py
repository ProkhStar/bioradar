import datetime as dt
import yfinance as yf
from agent.db.database import connect

def ingest(verbose=True):
    con=connect()
    tickers=[r[0] for r in con.execute("SELECT ticker FROM companies").fetchall()]
    raw=yf.download(tickers, period="3mo", auto_adjust=True, progress=False)
    # estrutura MultiIndex (Price, Ticker) -> pegar no bloco Close
    if isinstance(raw.columns, type(raw.columns)) and ("Close" in raw.columns.get_level_values(0)):
        close=raw["Close"]
    else:
        close=raw  # fallback: ja veio so Close
    n=0; fails=[]
    for tk in tickers:
        try:
            if tk not in close.columns: fails.append(tk); continue
            s=close[tk].dropna()
            if len(s)<2: fails.append(tk); continue
            price=float(s.iloc[-1]); prev=float(s.iloc[-2])
            chg_1d=(price/prev-1) if prev else None
            c30=float(s.iloc[-22]) if len(s)>=22 else float(s.iloc[0])
            chg_30d=(price/c30-1) if c30 else None
            asof=s.index[-1].date().isoformat()
            shares=None; mktcap=None
            try:
                fi=yf.Ticker(tk).fast_info
                shares=fi.get("shares") or fi.get("sharesOutstanding")
                if shares: mktcap=price*float(shares)
            except Exception: pass
            con.execute("INSERT OR REPLACE INTO prices(ticker,price,prev_close,chg_1d,chg_30d,mktcap,shares,asof) VALUES(?,?,?,?,?,?,?,?)",
                        (tk,price,prev,chg_1d,chg_30d,mktcap,shares,asof))
            n+=1
            if verbose:
                mc=f"${mktcap/1e9:.2f}B" if mktcap else "n/d"
                print(f"  {tk:5}: ${price:8.2f} | 1d {chg_1d:+.1%} | 30d {chg_30d:+.1%} | mktcap {mc}")
        except Exception:
            fails.append(tk)
    con.commit(); con.execute("INSERT INTO ingest_runs(source,n_new) VALUES('prices',?)",(n,)); con.commit(); con.close()
    if fails: print(f"  (sem precos: {fails})")
    return n
