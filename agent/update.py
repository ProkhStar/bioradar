import time
from agent.db.database import connect

def run_step(name, fn, results, verbose=True):
    if verbose: print(f"\n[{name}]")
    t0=time.time()
    try:
        r=fn(); results.append((name,"OK",str(r),time.time()-t0))
    except Exception as e:
        results.append((name,"ERRO",str(e),time.time()-t0))
        if verbose: print(f"  ERRO: {e}")

def update_all(skip_heavy=False, verbose=True):
    from agent.ingest.ingest_8k import ingest as i8k
    from agent.ingest.ingest_trials import ingest as itr
    from agent.ingest.ingest_prices import ingest as ipr
    from agent.ingest.ingest_fundamentals import ingest as ifu
    from agent.ingest.ingest_dilution import ingest as idi
    from agent.ingest.ingest_insiders import ingest as iin
    from agent.detect.detect_8k import process as det
    from agent.report.calendar import rebuild_calendar

    # ordem: primeiro o leve (metadados), depois deteccao, depois o pesado opcional
    steps=[
        ("ingest-8k", lambda: i8k(verbose=False)),
        ("ingest-trials", lambda: itr(verbose=False)[0]),
        ("ingest-prices", lambda: ipr(verbose=False)),
        ("ingest-fundamentals", lambda: ifu(verbose=False)),
        ("ingest-dilution", lambda: idi(verbose=False)),
        ("detect-8k", lambda: det(verbose=False)),
        ("rebuild-calendar", lambda: rebuild_calendar()),
    ]
    if not skip_heavy:
        steps.insert(5, ("ingest-insiders", lambda: iin(verbose=False)))

    print(f"=== UPDATE: {len(steps)} passos ({'sem' if skip_heavy else 'com'} insiders) ===")
    results=[]
    for name,fn in steps: run_step(name,fn,results,verbose)
    print("\n"+"="*52); print("RESUMO DA ATUALIZACAO:")
    ok=0
    for name,status,detail,dur in results:
        if status=="OK": ok+=1
        d=detail if len(detail)<40 else detail[:37]+"..."
        print(f"  {status:4} | {name:20} | {dur:5.1f}s | {d}")
    print(f"\n{ok}/{len(results)} passos OK")
    # registar a atualizacao
    con=connect(); con.execute("INSERT INTO ingest_runs(source,n_new) VALUES('UPDATE',?)",(ok,)); con.commit(); con.close()
    return results
