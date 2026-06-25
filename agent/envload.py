import os
def load_env(path=".env"):
    if not os.path.exists(path): return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line=line.lstrip("\ufeff").strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v=line.split("=",1)
            k=k.lstrip("\ufeff").strip(); v=v.strip().strip(chr(34)).strip(chr(39))
            if k: os.environ[k]=v
