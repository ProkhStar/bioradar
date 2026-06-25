import datetime as dt, json, os, html as _html
from agent.db.database import connect

def gather(con):
    today=dt.date.today()
    cal=[{"date":r[0],"days":(dt.date.fromisoformat(r[0])-today).days,"ticker":r[1],"type":r[2],"label":r[3]}
         for r in con.execute("SELECT cdate,ticker,ctype,label FROM catalysts WHERE cdate>=? AND cdate<=? ORDER BY cdate LIMIT 40",(today.isoformat(),(today+dt.timedelta(days=550)).isoformat())).fetchall()]
    alerts=[]; seen=set()
    for tk,fd,form in con.execute("SELECT ticker,filed_date,form FROM dilutions WHERE filed_date>=? ORDER BY filed_date DESC",((today-dt.timedelta(days=365)).isoformat(),)).fetchall():
        key=(tk,fd)
        if key in seen: continue
        f=con.execute("SELECT runway_quarters,stale FROM fundamentals WHERE ticker=?",(tk,)).fetchone()
        if f and f[0] and not f[1] and f[0]<6:
            seen.add(key); alerts.append({"ticker":tk,"date":fd,"form":form,"runway":round(f[0],1)})
    comps=[]
    for tk, in con.execute("SELECT ticker FROM companies ORDER BY ticker").fetchall():
        nm=con.execute("SELECT name FROM companies WHERE ticker=?",(tk,)).fetchone()[0]
        p=con.execute("SELECT price,chg_1d,chg_30d,mktcap FROM prices WHERE ticker=?",(tk,)).fetchone()
        f=con.execute("SELECT runway_quarters,stale,cash FROM fundamentals WHERE ticker=?",(tk,)).fetchone()
        ncs=[{"date":r[0],"type":r[1],"label":r[2]} for r in con.execute("SELECT cdate,ctype,label FROM catalysts WHERE ticker=? AND cdate>=? AND cdate<=? ORDER BY cdate LIMIT 4",(tk,today.isoformat(),(today+dt.timedelta(days=550)).isoformat())).fetchall()]
        ph=[{"phase":r[0],"n":r[1]} for r in con.execute("SELECT phase,COUNT(*) FROM trials WHERE ticker=? AND status NOT IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED') AND phase!='' GROUP BY phase ORDER BY phase DESC",(tk,)).fetchall()]
        ins=con.execute("SELECT COUNT(*),SUM(value) FROM insider_buys WHERE ticker=? AND txn_date>=date('now','-365 days')",(tk,)).fetchone()
        dil=con.execute("SELECT COUNT(*) FROM dilutions WHERE ticker=? AND filed_date>=date('now','-365 days')",(tk,)).fetchone()
        evs=[{"date":r[0],"type":r[1],"sent":r[2]} for r in con.execute("SELECT event_date,event_type,sentiment FROM events WHERE ticker=? ORDER BY event_date DESC LIMIT 5",(tk,)).fetchall()]
        memos=[r[0] for r in con.execute("SELECT memo_text FROM memos WHERE ticker=? ORDER BY event_id DESC LIMIT 3",(tk,)).fetchall()]
        comps.append({"ticker":tk,"name":nm,"price":p[0] if p else None,"chg1":p[1] if p else None,"chg30":p[2] if p else None,
                      "mktcap":p[3] if p else None,"runway":(round(f[0],1) if f and f[0] and not f[1] else None),
                      "stale":bool(f[1]) if f else False,"noburn":(f is not None and f[0] is None and not f[1]),
                      "cats":ncs,"pipeline":ph,"ins_n":ins[0] or 0,"ins_val":ins[1] or 0,"dil_n":dil[0] or 0,"events":evs,"memos":memos})
    return {"generated":today.isoformat(),"calendar":cal,"alerts":alerts,"companies":comps,
            "stats":{"companies":len(comps),"events":con.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                     "catalysts":con.execute("SELECT COUNT(*) FROM catalysts").fetchone()[0],
                     "insiders":con.execute("SELECT COUNT(*) FROM insider_buys").fetchone()[0]}}

HTML=r'''<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BIORADAR — Inteligencia Biotech</title>
<style>
:root{--bg:#0a0e14;--panel:#111720;--panel2:#0d131c;--line:#1e2733;--ink:#d4dae3;--dim:#7d8a9c;--mute:#4a5666;
--teal:#3fd0c9;--teal-d:#1a8f8a;--amber:#f5a623;--red:#ff5c5c;--green:#52d97f;--mono:"SF Mono",ui-monospace,"Cascadia Code","Roboto Mono",Menlo,Consolas,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:var(--mono);font-size:13px;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid var(--line);padding:22px 0 18px;position:sticky;top:0;background:linear-gradient(180deg,var(--bg) 80%,transparent);z-index:10}
.brand{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.logo{font-size:22px;font-weight:700;letter-spacing:3px;color:var(--teal)}
.logo b{color:var(--ink)}
.tag{color:var(--dim);font-size:11px;letter-spacing:1px}
.statline{margin-top:10px;display:flex;gap:20px;flex-wrap:wrap;color:var(--mute);font-size:11px}
.statline b{color:var(--ink)}
h2{font-size:11px;letter-spacing:2px;color:var(--dim);text-transform:uppercase;margin:34px 0 12px;font-weight:600;display:flex;align-items:center;gap:8px}
h2::before{content:"";width:6px;height:6px;background:var(--teal);border-radius:50%;box-shadow:0 0 8px var(--teal)}
/* calendario */
.cal{display:flex;gap:8px;overflow-x:auto;padding-bottom:8px}
.cal-item{flex:0 0 auto;min-width:150px;background:var(--panel);border:1px solid var(--line);border-left:2px solid var(--teal-d);padding:10px 12px;border-radius:3px}
.cal-item.pdufa{border-left-color:var(--amber)}
.cal-days{font-size:20px;font-weight:700;color:var(--ink)}
.cal-days span{font-size:10px;color:var(--mute);font-weight:400}
.cal-tk{color:var(--teal);font-weight:700;margin-top:4px}
.cal-lb{color:var(--dim);font-size:10px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cal-dt{color:var(--mute);font-size:10px;margin-top:6px}
.pill{display:inline-block;font-size:9px;letter-spacing:.5px;padding:1px 6px;border-radius:2px;text-transform:uppercase}
.pill.readout{background:rgba(63,208,201,.12);color:var(--teal)}
.pill.pdufa{background:rgba(245,166,35,.12);color:var(--amber)}
/* alertas */
.alerts{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}
.alert{background:var(--panel);border:1px solid var(--line);border-left:2px solid var(--red);padding:10px 12px;border-radius:3px}
.alert .tk{color:var(--red);font-weight:700}
.alert .d{color:var(--dim);font-size:11px;margin-top:3px}
/* grelha empresas */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.card{background:var(--panel);border:1px solid var(--line);padding:13px;border-radius:4px;cursor:pointer;transition:border-color .15s,transform .1s}
.card:hover{border-color:var(--teal-d);transform:translateY(-1px)}
.card-top{display:flex;justify-content:space-between;align-items:baseline}
.card-tk{font-size:15px;font-weight:700;color:var(--ink)}
.card-px{font-size:13px;color:var(--ink)}
.card-nm{color:var(--mute);font-size:10px;margin:2px 0 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row{display:flex;justify-content:space-between;font-size:11px;padding:2px 0;color:var(--dim)}
.row b{color:var(--ink);font-weight:500}
.up{color:var(--green)}.down{color:var(--red)}
.rw-short{color:var(--red)!important}.rw-ok{color:var(--green)!important}
.badge{display:inline-block;font-size:9px;padding:1px 5px;border-radius:2px;margin-top:8px;letter-spacing:.5px}
.badge.cat{background:rgba(63,208,201,.1);color:var(--teal)}
.badge.alert{background:rgba(255,92,92,.12);color:var(--red)}
/* modal */
.modal{position:fixed;inset:0;background:rgba(5,8,12,.85);display:none;z-index:50;padding:30px 16px;overflow-y:auto}
.modal.open{display:flex;align-items:flex-start;justify-content:center}
.sheet{background:var(--panel);border:1px solid var(--line);border-radius:6px;max-width:680px;width:100%;padding:24px}
.sheet h3{font-size:20px;color:var(--ink)}
.sheet .sub{color:var(--mute);font-size:11px;margin-bottom:16px}
.close{float:right;color:var(--dim);cursor:pointer;font-size:18px;line-height:1}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:6px 20px;margin:14px 0;padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.kv .row{font-size:12px}
.memo{background:var(--panel2);border:1px solid var(--line);border-radius:4px;padding:12px;margin-top:8px;font-size:12px;color:var(--ink);line-height:1.6}
.memo .src{color:var(--mute);font-size:10px;margin-top:6px}
.evlist{margin-top:6px}
.ev{display:flex;gap:10px;font-size:11px;padding:3px 0;color:var(--dim)}
.sent-pos{color:var(--green)}.sent-neg{color:var(--red)}.sent-misto{color:var(--amber)}.sent-neutro{color:var(--dim)}
footer{border-top:1px solid var(--line);margin-top:40px;padding:20px 0;color:var(--mute);font-size:10px;line-height:1.7}
.disc{color:var(--mute);font-size:10px;margin-top:6px;font-style:italic}
@media(max-width:560px){.kv{grid-template-columns:1fr}}
</style></head>
<body><div class="wrap">
<header><div class="brand"><div class="logo">BIO<b>RADAR</b></div><div class="tag">INTELIGENCIA DE CATALISADORES BIOTECH · DADOS PUBLICOS</div></div>
<div class="statline" id="stats"></div></header>
<main>
<h2>Proximos catalisadores</h2><div class="cal" id="cal"></div>
<h2>Alertas — diluicao com caixa curta</h2><div class="alerts" id="alerts"></div>
<h2>Universo — <span id="ccount" style="color:var(--teal)"></span> empresas</h2><div class="grid" id="grid"></div>
</main>
<footer>BIORADAR agrega filings da SEC (8-K, Form 4, 10-Q, 424B) e ensaios do ClinicalTrials.gov. Classificacao automatica; memos por LLM a partir de factos extraidos.<br>
Gerado em <span id="gen"></span>. Nao constitui recomendacao de investimento — ferramenta de investigacao com revisao humana.</footer>
</div>
<div class="modal" id="modal"><div class="sheet" id="sheet"></div></div>
<script>
const DATA=__DATA__;
const fmtM=v=>v?("$"+(v/1e9>=1?(v/1e9).toFixed(1)+"B":(v/1e6).toFixed(0)+"M")):"n/d";
const pct=v=>v==null?"":(v>=0?'<span class="up">+'+(v*100).toFixed(1)+'%</span>':'<span class="down">'+(v*100).toFixed(1)+'%</span>');
function rwTxt(c){if(c.stale)return'<span style="color:var(--mute)">dados antigos</span>';if(c.noburn)return'<span class="rw-ok">fluxo+</span>';if(c.runway==null)return"n/d";const m=Math.round(c.runway*3);return'<span class="'+(c.runway<6?'rw-short':'rw-ok')+'">'+(c.runway>20?'+60m':'~'+m+'m')+'</span>';}
// stats
const s=DATA.stats;document.getElementById('stats').innerHTML=`<span><b>${s.companies}</b> empresas</span><span><b>${s.catalysts}</b> catalisadores</span><span><b>${s.events}</b> eventos</span><span><b>${s.insiders}</b> compras insiders</span>`;
document.getElementById('gen').textContent=DATA.generated;document.getElementById('ccount').textContent=DATA.companies.length;
// calendario
document.getElementById('cal').innerHTML=DATA.calendar.map(c=>`<div class="cal-item ${c.type}"><div class="cal-days">${c.days}<span>d</span></div><div class="cal-tk">${c.ticker}</div><div class="cal-lb">${c.label}</div><div class="cal-dt"><span class="pill ${c.type}">${c.type}</span> ${c.date}</div></div>`).join('')||'<div style="color:var(--mute)">sem catalisadores proximos</div>';
// alertas
document.getElementById('alerts').innerHTML=DATA.alerts.map(a=>`<div class="alert"><div class="tk">${a.ticker}</div><div class="d">${a.form} em ${a.date}<br>runway ~${Math.round(a.runway*3)} meses</div></div>`).join('')||'<div style="color:var(--mute)">sem alertas</div>';
// grelha
document.getElementById('grid').innerHTML=DATA.companies.map((c,i)=>{
  let badges='';if(c.cats.length)badges+=`<span class="badge cat">prox: ${c.cats[0].date.slice(0,7)}</span> `;if(c.dil_n&&c.runway!=null&&c.runway<6)badges+=`<span class="badge alert">diluicao</span>`;
  return `<div class="card" onclick="openC(${i})"><div class="card-top"><span class="card-tk">${c.ticker}</span><span class="card-px">${c.price?'$'+c.price.toFixed(2):''}</span></div><div class="card-nm">${c.name}</div>
  <div class="row"><span>30d</span><b>${pct(c.chg30)||'n/d'}</b></div><div class="row"><span>mktcap</span><b>${fmtM(c.mktcap)}</b></div><div class="row"><span>runway</span><b>${rwTxt(c)}</b></div><div>${badges}</div></div>`;
}).join('');
// modal
function openC(i){const c=DATA.companies[i];
  let cats=c.cats.length?c.cats.map(x=>`<div class="ev"><span style="color:var(--teal)">${x.date}</span><span class="pill ${x.type}">${x.type}</span> ${x.label}</div>`).join(''):'<div style="color:var(--mute);font-size:11px">sem catalisadores agendados</div>';
  let evs=c.events.length?c.events.map(e=>`<div class="ev"><span>${e.date}</span><span>${e.type}</span><span class="sent-${e.sent}">${e.sent}</span></div>`).join(''):'<div style="color:var(--mute);font-size:11px">sem eventos</div>';
  let pl=c.pipeline.map(p=>p.phase+": "+p.n).join(" · ")||"n/d";
  let memos=c.memos.length?c.memos.map(m=>`<div class="memo">${m.replace(/\*\*/g,'').replace(/\n/g,'<br>')}</div>`).join(''):'<div style="color:var(--mute);font-size:11px">sem memos gerados</div>';
  document.getElementById('sheet').innerHTML=`<span class="close" onclick="closeC()">✕</span><h3>${c.ticker}</h3><div class="sub">${c.name}</div>
  <div class="kv"><div class="row"><span>preco</span><b>${c.price?'$'+c.price.toFixed(2):'n/d'} ${pct(c.chg1)}</b></div><div class="row"><span>30 dias</span><b>${pct(c.chg30)||'n/d'}</b></div>
  <div class="row"><span>market cap</span><b>${fmtM(c.mktcap)}</b></div><div class="row"><span>cash runway</span><b>${rwTxt(c)}</b></div>
  <div class="row"><span>pipeline</span><b>${pl}</b></div><div class="row"><span>insiders 12m</span><b>${c.ins_n} ($${(c.ins_val/1e6).toFixed(1)}M)</b></div></div>
  <h2 style="margin:6px 0 4px">Proximos catalisadores</h2>${cats}
  <h2 style="margin:14px 0 4px">Eventos recentes</h2><div class="evlist">${evs}</div>
  <h2 style="margin:14px 0 4px">Memos</h2>${memos}
  <div class="disc">Classificacao automatica a partir de dados publicos; rever nos filings originais. Nao e recomendacao de investimento.</div>`;
  document.getElementById('modal').classList.add('open');}
function closeC(){document.getElementById('modal').classList.remove('open');}
document.getElementById('modal').addEventListener('click',e=>{if(e.target.id=='modal')closeC();});
document.addEventListener('keydown',e=>{if(e.key=='Escape')closeC();});
</script></body></html>'''

def build(verbose=True):
    con=connect(); data=gather(con); con.close()
    os.makedirs("site", exist_ok=True)
    out=HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    with open("site/index.html","w",encoding="utf-8") as f: f.write(out)
    if verbose: print(f"site/index.html gerado: {data['stats']['companies']} empresas, {len(data['calendar'])} catalisadores, {len(data['alerts'])} alertas")
    return "site/index.html"

