import os, json, urllib.request
from agent.db.database import connect

GROQ_MODEL=os.environ.get("GROQ_MODEL","openai/gpt-oss-120b")
TYPE_PT={"readout":"Resultados de ensaio (readout)","regulatory":"Evento regulatorio (FDA)","designation":"Designacao regulatoria"}
SENT_PT={"pos":"positivo","neg":"negativo","misto":"misto","neutro":"neutro"}

def build_context(con, ev):
    eid,tk,etype,edate,ref,summary,sent=ev
    r=con.execute("SELECT name FROM companies WHERE ticker=?",(tk,)).fetchone(); name=r[0] if r else tk
    p=con.execute("SELECT price,chg_30d,mktcap FROM prices WHERE ticker=?",(tk,)).fetchone()
    f=con.execute("SELECT runway_quarters,stale FROM fundamentals WHERE ticker=?",(tk,)).fetchone()
    nc=con.execute("SELECT cdate,label FROM catalysts WHERE ticker=? AND cdate>? ORDER BY cdate LIMIT 1",(tk,edate)).fetchone()
    return {"eid":eid,"ticker":tk,"name":name,"etype":etype,"edate":edate,"sentiment":sent,"signals":summary,"ref":ref,
            "price":p[0] if p else None,"chg30":p[1] if p else None,"mktcap":p[2] if p else None,
            "runway":(f[0] if f and not f[1] else None),"next_cat":(f"{nc[1]} em {nc[0]}" if nc else None)}

def template_memo(c):
    L=[f"**[{c['ticker']}] {TYPE_PT.get(c['etype'],c['etype'])} — {c['edate']}**"]
    L.append(f"{c['name']} divulgou um 8-K classificado como {TYPE_PT.get(c['etype'],c['etype']).lower()} (sentimento detetado: {SENT_PT.get(c['sentiment'],c['sentiment'])}).")
    ctx=[]
    if c["price"]: ctx.append(f"cotacao ${c['price']:.2f}"+(f" ({c['chg30']:+.0%} em 30d)" if c['chg30'] is not None else ""))
    if c["runway"] is not None: ctx.append(f"runway ~{c['runway']*3:.0f} meses"+(" (CURTO)" if c['runway']<6 else ""))
    if ctx: L.append("Contexto: "+"; ".join(ctx)+".")
    if c["next_cat"]: L.append(f"Proximo catalisador: {c['next_cat']}.")
    L.append(f"_Classificacao automatica por regras (accession {c['ref']}); rever no filing original. Nao e recomendacao de investimento._")
    return "\n".join(L)

def groq_prompt(c):
    factos=[f"Empresa: {c['name']} ({c['ticker']})", f"Tipo de evento (8-K): {TYPE_PT.get(c['etype'],c['etype'])}",
            f"Sentimento detetado: {SENT_PT.get(c['sentiment'],c['sentiment'])}", f"Sinais no texto: {c['signals']}", f"Data: {c['edate']}"]
    if c["price"]: factos.append(f"Cotacao: ${c['price']:.2f}"+(f", {c['chg30']:+.0%} em 30 dias" if c['chg30'] is not None else ""))
    if c["runway"] is not None: factos.append(f"Cash runway: ~{c['runway']*3:.0f} meses"+(" (CURTO - risco de diluicao)" if c['runway']<6 else ""))
    if c["next_cat"]: factos.append(f"Proximo catalisador agendado: {c['next_cat']}")
    return ("Es um analista de biotech. Escreve uma nota curta (3-4 frases, portugues europeu de Portugal) que sintetiza "
            "APENAS os factos abaixo, explicando porque o evento pode importar para a empresa. Nao inventes nada para alem dos factos dados. "
            "Termina com um aviso breve de que e analise automatica, nao recomendacao de investimento.\n\nFACTOS:\n- "+"\n- ".join(factos))

def groq_memo(c, timeout=30):
    key=os.environ.get("GROQ_API_KEY")
    if not key: return None
    body=json.dumps({"model":GROQ_MODEL,"temperature":0.3,"max_completion_tokens":1200,
                     "messages":[{"role":"system","content":"Es um analista de biotech rigoroso e conciso."},
                                 {"role":"user","content":groq_prompt(c)}]}).encode("utf-8")
    req=urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body,
                               headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        resp=json.loads(urllib.request.urlopen(req,timeout=timeout).read().decode("utf-8"))
        txt=resp["choices"][0]["message"]["content"].strip()
        return f"**[{c['ticker']}] {TYPE_PT.get(c['etype'],c['etype'])} — {c['edate']}**\n"+txt
    except Exception as e:
        print(f"    (Groq falhou: {e} -> fallback template)")
        return None

def generate(generator="auto", limit=None, verbose=True):
    con=connect()
    q="SELECT id,ticker,event_type,event_date,ref,summary,sentiment FROM events WHERE memo_status!='done' ORDER BY event_date DESC"
    if limit: q+=f" LIMIT {int(limit)}"
    evs=con.execute(q).fetchall()
    use_groq = (generator=="groq") or (generator=="auto" and os.environ.get("GROQ_API_KEY"))
    print(f"eventos sem memo: {len(evs)} | gerador: {'Groq ('+GROQ_MODEL+')' if use_groq else 'template'}")
    n=0
    for ev in evs:
        c=build_context(con,ev); memo=None; gen="template"
        if use_groq:
            memo=groq_memo(c)
            if memo: gen="groq"
        if not memo: memo=template_memo(c)
        con.execute("INSERT OR REPLACE INTO memos(event_id,ticker,memo_text,generator) VALUES(?,?,?,?)",(c["eid"],c["ticker"],memo,gen))
        con.execute("UPDATE events SET memo_status='done' WHERE id=?",(c["eid"],)); n+=1
        if n%50==0: con.commit(); print(f"  ... {n}/{len(evs)}")
    con.commit(); con.close()
    return n

def show(ticker=None, limit=10):
    con=connect()
    if ticker:
        rows=con.execute("SELECT memo_text,generator FROM memos WHERE ticker=? ORDER BY event_id DESC LIMIT ?",(ticker.upper(),limit)).fetchall()
    else:
        rows=con.execute("SELECT memo_text,generator FROM memos ORDER BY event_id DESC LIMIT ?",(limit,)).fetchall()
    for txt,gen in rows: print(txt+f"\n   [gerado por: {gen}]\n"+"-"*64)
    con.close()


