#!/usr/bin/env python3
# Robot que arma el calendario de limpiezas de Wanderhaus desde los iCal de Airbnb.
# Corre en GitHub Actions. No necesita librerias externas (solo Python estandar).
import os, re, json, datetime, urllib.request

# --- Catalogo: CLAVE -> (nombre visible, grupo, recamaras) ---
CAT = {
 "AMB-01":("Amberjack 1","Amberjack","2 rec"), "AMB-02":("Amberjack 2","Amberjack","2 rec"),
 "AMB-03":("Amberjack 3","Amberjack","2 rec"), "AMB-04":("Amberjack 4","Amberjack","2 rec"),
 "AMB-05":("Amberjack 5","Amberjack","3 rec"), "AMB-06":("Amberjack 6","Amberjack","3 rec"),
 "AMB-07":("Amberjack 7","Amberjack","3 rec"), "AMB-08":("Amberjack 8","Amberjack","3 rec"),
 "DOL-1A":("Sol Azul 1A","Sol Azul","condo"), "DOL-1B":("Sol Azul 1B","Sol Azul","condo"),
 "DOL-2A":("Sol Azul 2A","Sol Azul","condo"), "DOL-2B":("Sol Azul 2B","Sol Azul","condo"),
 "FDS-01":("Fiesta del Sol","Fiesta del Sol","condo"),
}

def load_feeds():
    """Lee el secreto AIRBNB_FEEDS: lineas con 'CLAVE url' (espacios o tab)."""
    raw = os.environ.get("AIRBNB_FEEDS","").strip()
    feeds={}
    for line in raw.splitlines():
        line=line.strip()
        if not line or line.startswith("#"): continue
        parts=line.split(None,1)
        if len(parts)==2:
            feeds[parts[0].strip().upper()]=parts[1].strip()
    return feeds

def fetch(url):
    req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (Wanderhaus calendar bot)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8","ignore")

def unfold(text):
    # iCal dobla lineas largas con CRLF + espacio/tab. Las volvemos a unir.
    return text.replace("\r\n"," \n").replace("\n ","").replace("\n\t","")

def parse_reservations(ics):
    """Devuelve lista de (checkin_date, checkout_date) solo de reservas (no bloqueos)."""
    ics=unfold(ics)
    out=[]
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics, re.S):
        summ=(re.search(r"SUMMARY:(.*)", block) or [None,""])[1].strip().lower()
        desc=(re.search(r"DESCRIPTION:(.*)", block) or [None,""])[1].strip().lower()
        is_res = ("reserved" in summ) or ("reservation" in desc) or ("/details/" in desc)
        if not is_res:  # saltar bloqueos "Not available"
            continue
        ds=re.search(r"DTSTART[^:]*:(\d{8})", block); de=re.search(r"DTEND[^:]*:(\d{8})", block)
        if not (ds and de): continue
        ci=datetime.datetime.strptime(ds.group(1),"%Y%m%d").date()
        co=datetime.datetime.strptime(de.group(1),"%Y%m%d").date()
        out.append((ci,co))
    return out

def build():
    feeds=load_feeds()
    today=datetime.date.today()
    rows=[]
    for clave,url in feeds.items():
        if clave not in CAT: 
            print("AVISO: clave desconocida, la salto:",clave); continue
        name,group,beds=CAT[clave]
        try:
            res=parse_reservations(fetch(url))
        except Exception as e:
            print("ERROR leyendo",clave,e); continue
        # quitar reservas modificadas que quedan duplicadas: misma entrada -> la mas larga
        bystart={}
        for ci,co in res:
            if ci not in bystart or co>bystart[ci]: bystart[ci]=co
        res=[(ci,co) for ci,co in bystart.items()]
        checkins={ci for ci,_ in res}
        for ci,co in res:
            if co<today: continue
            rows.append({"date":co.isoformat(),"unit":clave,"name":name,"group":group,
                         "beds":beds,"turnover":(co in checkins)})
        print(f"{clave}: {len(res)} reservas")
    rows.sort(key=lambda x:(x["date"],x["group"],x["name"]))
    data=json.dumps(rows,ensure_ascii=False,separators=(",",":"))
    tpl=open("template.html",encoding="utf-8").read()
    html=tpl.replace("__DATA__",data).replace("__UPDATED__",today.strftime("%d/%m/%Y"))
    open("index.html","w",encoding="utf-8").write(html)
    print(f"OK: index.html con {len(rows)} salidas, {sum(r['turnover'] for r in rows)} turnovers")

if __name__=="__main__":
    build()
