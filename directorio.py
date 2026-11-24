"""Vista Directorio: consolidado de calidad de toda la cosecha, para presentar.
Arma una pagina HTML (avance, cajas, categoria, calibre, color, brix inicio/fin y limpieza) a partir
de las tablas de cosecha ya cargadas. No depende de Streamlit."""
from html import escape

import pandas as pd

import cosecha_calc as cc

PAL = ["#5b8def", "#9b7be0", "#e8975a", "#4fb8a8", "#d9668a", "#a3b84f", "#7a8691", "#c9a24a"]
COLV = {"Timpson": "#6aa84f", "Allison": "#d0638a", "Candy Hearts": "#e9a2c4", "Red Globe": "#b04646",
        "Autumn Crisp": "#d9b230", "Cotton Candy": "#7fb3d5", "Sugra 54": "#3f9a8f"}
GC = {"Condición": "#ee8f86", "Calidad": "#f6c56f", "Plagas": "#b7a0dc"}
CB = {"Bajo": "#ee8f86", "Tolerable": "#f6c56f", "Óptimo": "#7cc99a", "Exceso": "#b7a0dc"}
CAT = {"Cat 1": "#55b67c", "Cat 1.5": "#f0b450", "Cat 2": "#e7776f", "Descarte": "#6b6461"}
BAYA = {"Verde": "#8cc152", "Cremoso": "#dcd685", "Ámbar": "#e2a83a", "Full color oscuro": "#6a1640",
        "Full color claro": "#a8285c", "Aureola cremosa r oscuro": "#b8306a", "Aureola cremosa r claro": "#d9608a",
        "Aureola verde": "#9bb85a", "Color intermedio": "#e07aa6", "Falta de color": "#cfd9c8"}

CSS = """
:root{--bg:#f3f1ee;--card:#fff;--fg:#1f1b1a;--mut:#6d6663;--line:#e6e1dc;--track:#eeeae6;--acc:#c8102e;
  --ff:Inter,"Segoe UI",system-ui,sans-serif;--fd:"Space Grotesk",Inter,"Segoe UI",sans-serif}
:root[data-theme="dark"]{--bg:#141112;--card:#1e1a1b;--fg:#f2ece9;--mut:#a89f9b;--line:#332c2d;--track:#2c2627;--acc:#ff5a6e;color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--ff)}
.w{max-width:1180px;margin:0 auto;padding:20px max(16px,env(safe-area-inset-left,0px)) 40px;display:flex;flex-direction:column;gap:18px}
.hd{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:18px;color:#fff;border-radius:14px;padding:16px 26px;
  background:linear-gradient(100deg,#c8102e 0%,#a3112a 45%,#5e0d18 100%)}
.wm{font:700 2rem/1 Georgia,serif} .tg{font:italic 600 .8rem Georgia,serif;text-align:right}
.ttl{text-align:center} .ttl h1{margin:0;font-weight:800;font-size:clamp(1.2rem,2.6vw,1.9rem);letter-spacing:.04em;text-transform:uppercase}
.ttl p{margin:4px 0 0;opacity:.9;font-size:.9rem} .upd{text-align:right} .upd span{display:block;font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;opacity:.85}
.upd b{font-size:1.35rem}
@media(max-width:760px){.hd{grid-template-columns:1fr;text-align:center}.upd,.tg{text-align:center}}
.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px} @media(max-width:900px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
.k{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.k .l{font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
.k .v{font-family:var(--fd);font-size:clamp(1.5rem,3vw,2.2rem);font-weight:700;font-variant-numeric:tabular-nums} .k .s{font-size:.82rem;color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;min-width:0}
.card h2{margin:0;font-family:var(--fd);font-size:1.3rem;display:flex;align-items:baseline;gap:10px}
.card h2 em{font-style:normal;font-size:.8rem;font-weight:700;color:#fff;background:var(--acc);border-radius:99px;padding:2px 10px;font-family:var(--ff)}
.card .sub{color:var(--mut);font-size:.88rem;margin:4px 0 16px}
.duo{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px} @media(max-width:900px){.duo{grid-template-columns:1fr}}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.92rem;font-variant-numeric:tabular-nums}
th{text-align:left;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);border-bottom:2px solid var(--fg);padding:8px;white-space:nowrap}
td{padding:9px 8px;border-bottom:1px solid var(--line)} td span{display:block;font-size:.74rem;color:var(--mut)} .n{text-align:right}
tr.tot td{border-top:2px solid var(--fg);border-bottom:none;font-weight:800}
.est{display:inline-block!important;padding:3px 10px;border-radius:99px;font-size:.74rem!important;font-weight:700;color:#fff!important}
.est.t{background:#3e9e62} .est.c{background:#d98e1f}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
.hbars{display:flex;flex-direction:column;gap:12px}
.hb{display:grid;grid-template-columns:96px minmax(0,1fr) 108px;align-items:center;gap:12px}
.lb{font-weight:800;font-size:1.05rem} .lb small{display:block;font-weight:500;font-size:.74rem;color:var(--mut)}
.vv{text-align:right;font-weight:800;font-size:1.1rem;font-variant-numeric:tabular-nums} .vv small{display:block;font-weight:500;font-size:.72rem;color:var(--mut)}
.tr{height:26px;background:var(--track);border-radius:6px;overflow:hidden} .tr i{display:block;height:100%;border-radius:6px}
.st{display:flex;height:28px;border-radius:6px;overflow:hidden;background:var(--track)}
.st i{display:flex;align-items:center;justify-content:center;color:#2a1d1b;font-style:normal;font-weight:700;font-size:.76rem;min-width:0;overflow:hidden}
.st i.dk{color:#fff}
.t3{display:flex;flex-wrap:wrap;gap:3px 14px;margin-top:6px;font-size:.8rem;color:var(--mut)} .t3 b{color:var(--fg)}
.t3 i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px}
.bxr{display:grid;grid-template-columns:104px minmax(0,1fr) 50px;gap:8px;align-items:center;margin:3px 0}
.bxd{font-size:.78rem;font-weight:700;white-space:nowrap} .bxd small{font-weight:500;color:var(--mut);margin-left:4px}
.bxp{font-weight:800;text-align:right;font-variant-numeric:tabular-nums} .bxr .st{height:22px}
.blk{padding:6px 0;border-bottom:1px solid var(--line)} .blk:last-child{border-bottom:none}
.ley{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:14px;font-size:.8rem;color:var(--mut)}
.ley i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.tema{position:absolute;top:12px;right:12px;border:1px solid rgba(255,255,255,.5);background:rgba(255,255,255,.12);color:#fff;
  border-radius:99px;padding:4px 12px;font:600 .78rem var(--ff);cursor:pointer} .hd{position:relative}
.vcols{display:flex;align-items:flex-end;gap:14px;overflow-x:auto;padding:4px 2px 2px}
.vc{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:70px;flex:1 0 70px;max-width:120px}
.vc .bar{width:46px;height:220px;display:flex;flex-direction:column-reverse;border-radius:8px;overflow:hidden;background:var(--track)}
.vc .bar i{display:flex;align-items:center;justify-content:center;font-style:normal;font-size:.72rem;font-weight:700;color:#2a1d1b}
.vc .bar i.dk{color:#fff} .vc b{font-size:.95rem} .vc small{font-size:.7rem;color:var(--mut);margin-top:-4px;white-space:nowrap;max-width:80px;overflow:hidden;text-overflow:ellipsis}
.vc .top{font-family:var(--fd);font-weight:700;font-size:1.05rem}
.bxg{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.bx{background:var(--track);border-radius:12px;padding:12px 14px}
.bx .h{display:flex;justify-content:space-between;align-items:baseline} .bx .h b{font-size:1rem} .bx .h span{font-size:.72rem;color:var(--mut)}
.bx .vals{display:flex;align-items:baseline;gap:8px;margin:6px 0 8px;font-family:var(--fd)}
.bx .vals .a{font-size:1.15rem;color:var(--mut)} .bx .vals .z{font-size:1.75rem;font-weight:700}
.bx .vals .d{font-size:.8rem;font-weight:700;font-family:var(--ff);margin-left:auto;padding:2px 7px;border-radius:99px}
.esc{position:relative;height:10px;border-radius:5px;background:linear-gradient(90deg,#ee8f86 0 var(--t),#f6c56f var(--t) var(--o),#7cc99a var(--o) 100%)}
.esc i{position:absolute;top:50%;width:12px;height:12px;border-radius:50%;transform:translate(-50%,-50%);border:2px solid var(--card)}
.esc i.a{background:var(--card);border:2px solid var(--fg)} .esc i.z{background:var(--fg);width:15px;height:15px}
.bx .pc{display:flex;justify-content:space-between;font-size:.7rem;color:var(--mut);margin-top:6px}
.hm{border-collapse:separate;border-spacing:4px;width:auto;min-width:100%}
.hm th{border:none;text-align:center;font-size:.8rem;color:var(--fg);text-transform:none;letter-spacing:0;padding:6px 4px}
.hm th small{display:block;font-weight:500;color:var(--mut);font-size:.68rem}
.hm td{border:none;text-align:center;border-radius:8px;padding:9px 6px;font-weight:700;font-size:.86rem;min-width:62px}
.hm td.dn{text-align:left;font-weight:600;color:var(--fg);background:none;padding-right:12px;white-space:nowrap}
.hm tr.res td{font-size:1rem;font-family:var(--fd)} .hm td.z{color:var(--mut);font-weight:500}
.hm td.tot{background:#e7776f;color:#fff;font-size:1.15rem;font-family:var(--fd)}
.hm td.cal{background:#55b67c;color:#fff;font-size:1.15rem;font-family:var(--fd)}
.hm tr.res td.dn{font-family:var(--fd);font-size:1rem;font-weight:700}
.hm td.sep{text-align:left;background:none;color:var(--mut);font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;padding:12px 0 2px}
.pzg{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.pz{background:var(--track);border-radius:12px;padding:14px 16px}
.pz .h{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px} .pz .h b{font-size:1.05rem} .pz .h span{font-size:.74rem;color:var(--mut)}
.pms{display:grid;grid-template-columns:1fr 1fr;gap:12px 10px}
.pm{display:flex;align-items:center;gap:8px} .pm svg{flex:none}
.pm b{display:block;font-family:var(--fd);font-size:1.25rem;line-height:1.1;font-variant-numeric:tabular-nums}
.pm b small{font-size:.75rem;color:var(--mut);margin-left:2px;font-family:var(--ff)} .pm span{font-size:.7rem;color:var(--mut)}
.big3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:14px}
.big3 div{background:var(--track);border-radius:10px;padding:10px 12px} .big3 b{display:block;font-family:var(--fd);font-size:1.6rem}
.big3 span{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);font-weight:700}
"""

UVA = ("<svg width='40' height='50' viewBox='0 0 48 60' aria-hidden='true'><path d='M24 3v7M24 7c4-4 9-4 13-1' stroke='#7cbf3a' "
       "stroke-width='3' fill='none' stroke-linecap='round'/><g fill='#9fd45a' stroke='#5f9e2c' stroke-width='1.2'>"
       + "".join(f"<circle cx='{x}' cy='{y}' r='6'/>" for x, y in
                 [(13, 17), (24, 16), (35, 17), (18, 27), (30, 27), (12, 37), (24, 37), (36, 37), (18, 47), (30, 47), (24, 55)])
       + "</g></svg>")


I_JABA = ("<svg width='30' height='30' viewBox='0 0 24 24' fill='none' stroke='#e8975a' stroke-width='1.8' stroke-linecap='round' "
          "stroke-linejoin='round' aria-hidden='true'><path d='M3 9h18l-2 12H5z'/><path d='M2 9h20M6 13.5h12M7 17.5h10M9.5 9v12M14.5 9v12'/>"
          "<circle cx='8' cy='5.5' r='2' fill='#e8975a' stroke='none'/><circle cx='12' cy='4.6' r='2' fill='#e8975a' stroke='none'/>"
          "<circle cx='16' cy='5.5' r='2' fill='#e8975a' stroke='none'/></svg>")
I_RACIMO = ("<svg width='30' height='30' viewBox='0 0 24 24' aria-hidden='true'><path d='M12 1.5v3.5M12 3.2c2-1.6 4.4-1.6 6-.4' stroke='#6aa84f' "
            "stroke-width='1.8' fill='none' stroke-linecap='round'/>" + "".join(f"<circle cx='{x}' cy='{y}' r='2.6' fill='#b9467a'/>" for x, y in
            [(7, 8), (12, 7.6), (17, 8), (9.5, 12.6), (14.5, 12.6), (7, 17), (12, 17), (17, 17), (12, 21.2)]) + "</svg>")
I_BAYAS = ("<svg width='30' height='30' viewBox='0 0 24 24' aria-hidden='true'><circle cx='8' cy='9' r='4.5' fill='#7cc99a'/>"
           "<circle cx='16.5' cy='13' r='3.5' fill='#7cc99a'/><circle cx='9' cy='19' r='2.6' fill='#7cc99a'/>"
           "<text x='16' y='23' font-size='7' font-weight='800' fill='#7cc99a' font-family='sans-serif'>n°</text></svg>")
I_BAYA = ("<svg width='30' height='30' viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='8' fill='#55b67c'/>"
          "<circle cx='9' cy='9' r='2.4' fill='#fff' opacity='.4'/></svg>")


def _card(tit, sub, body, tag=""):
    em = f"<em>{tag}</em>" if tag else ""
    sb = f"<p class='sub'>{sub}</p>" if sub else "<div style='height:12px'></div>"
    return f"<section class='card'><h2>{tit}{em}</h2>{sb}{body}</section>"


def _st(partes, colores, oscuros=()):
    s = sum(v for _, v in partes if v and pd.notna(v)) or 1
    return "<div class='st'>" + "".join(
        f"<i class='{'dk' if n in oscuros else ''}' title='{escape(str(n))}: {v:.1f}%' style='width:{v / s * 100:.2f}%;"
        f"background:{colores.get(n, '#9a9290')}'>{f'{v / s * 100:.0f}%' if v / s >= .07 else ''}</i>"
        for n, v in partes if v and v > 0) + "</div>"


def _ley(colores):
    return "<div class='ley'>" + "".join(f"<span><i style='background:{c}'></i>{escape(str(n))}</span>" for n, c in colores.items()) + "</div>"


def agrupar_por_variedad(lotes):
    """Une los lotes de cada variedad en un solo grupo (para ver el consolidado por variedad)."""
    F = pd.DataFrame(lotes)
    out = []
    for v, g in F.groupby("var"):
        out.append({"l": list(g["l"]), "corto": v, "var": f"{len(g)} lote{'s' if len(g) > 1 else ''}", "var_cod": g["var_cod"].iloc[0],
                    "fundo": ", ".join(sorted(g["fundo"].unique())), "est": "Terminada" if (g["est"] == "Terminada").all() else "En cosecha",
                    "ini": g["ini"].min(), "fin": g["fin"].max(), "dias": int(g["dias"].max()), "ha": g["ha"].sum(),
                    "cajas": g["cajas"].sum(), "n_term": int((g["est"] == "Terminada").sum()), "n_cos": int((g["est"] != "Terminada").sum())})
    return sorted(out, key=lambda x: -x["cajas"])


def html_directorio(lotes, T, tema="dark", fecha_corte=None, generado="", titulo_extra="", por="lote"):
    """lotes: lista de dicts {l, corto, fundo, var, est ('Terminada'|'En cosecha'), ini, fin, dias, ha, cajas, var_cod}.
    T: {clave: DataFrame con lote_id y _fecha} de cosecha_calc.TABLAS. por: 'lote' o 'variedad'."""
    lotes_orig = lotes
    if por == "variedad":
        lotes = agrupar_por_variedad(lotes)
    F = pd.DataFrame(lotes)
    if F.empty:
        return "<p>Sin lotes con cosecha.</p>"
    if por == "lote":
        F = F.sort_values(["est", "corto"], ascending=[False, True])
    ids = lambda l: l if isinstance(l, list) else [l]
    sub = lambda k, l: T[k][T[k]["lote_id"].isin(ids(l))] if k in T and len(T[k]) else pd.DataFrame()
    todos = [x for l in F["l"] for x in ids(l)]
    tot = F["cajas"].sum()
    ha_c = F.loc[F["cajas"] > 0, "ha"].sum()

    # ---- cifras
    c1_tot = []
    for l in F["l"]:
        g = sub("categoria", l)
        r = cc.categoria(g) if len(g) else None
        if r:
            cats = dict(r["categorias"])
            c1_tot.append((cats.get("Cat 1", 0) + cats.get("Cat 1 Premium", 0), r["muestras"]))
    cat1 = sum(a * b for a, b in c1_tot) / max(1, sum(b for _, b in c1_tot)) if c1_tot else None
    L = T.get("limpieza", pd.DataFrame())
    L = L[L["lote_id"].isin(todos)] if len(L) else L
    rlim = cc.desviacion(L, "racimos-por-jaba", {}) if len(L) else None
    Fl = pd.DataFrame(lotes_orig)
    kp = [("Lotes cosechados", f"{len(Fl)}", f"{(Fl.est == 'Terminada').sum()} terminados · {(Fl.est != 'Terminada').sum()} en cosecha"),
          ("Cajas equivalentes", f"{tot:,.0f}", "producción en packing"),
          ("Cajas por hectárea", f"{tot / ha_c:,.0f}" if ha_c else "—", f"sobre {ha_c:,.1f} ha con cajas"),
          ("Categoría 1", f"{cat1:.0f}%" if cat1 is not None else "—", "de los racimos (categorización)"),
          ("Calidad lograda", f"{rlim['calidad']:.1f}%" if rlim else "—", f"desviación {rlim['desviacion']:.1f}% en limpieza" if rlim else "")]
    kpis = "<section class='kpis'>" + "".join(
        f"<div class='k'><div class='l'>{a}</div><div class='v'>{b}</div><div class='s'>{c}</div></div>" for a, b, c in kp) + "</section>"

    # ---- avance
    filas = "".join(
        f"<tr><td><b>Lote {r.corto[1:]}</b><span>{r.fundo}</span></td><td><i class='dot' style='background:{COLV.get(r.var, '#9a9290')}'></i>{r.var}</td>"
        f"<td><span class='est {'t' if r.est == 'Terminada' else 'c'}'>{r.est}</span></td><td>{r.ini:%d/%m}</td>"
        f"<td>{r.fin:%d/%m}{'' if r.est == 'Terminada' else ' <small>(último)</small>'}</td><td class='n'>{r.dias}</td>"
        f"<td class='n'>{r.ha:,.1f}</td><td class='n'><b>{f'{r.cajas:,.0f}' if r.cajas else '—'}</b></td>"
        f"<td class='n'>{f'{r.cajas / r.ha:,.0f}' if r.cajas and r.ha else '—'}</td></tr>" for r in F.itertuples())
    filas += (f"<tr class='tot'><td>Total</td><td></td><td>{(F.est == 'Terminada').sum()} term. · {(F.est != 'Terminada').sum()} en cosecha</td>"
              f"<td>{F.ini.min():%d/%m}</td><td>{F.fin.max():%d/%m}</td><td></td><td class='n'>{F.ha.sum():,.1f}</td>"
              f"<td class='n'>{tot:,.0f}</td><td class='n'>{tot / ha_c:,.0f}</td></tr>" if ha_c else "")
    if por == "variedad":
        filas = "".join(
            f"<tr><td><b><i class='dot' style='background:{COLV.get(r.corto, '#9a9290')}'></i>{r.corto}</b><span>{r.fundo}</span></td>"
            f"<td class='n'>{len(r.l)}</td><td><span class='est t'>{r.n_term}</span> <span class='est c'>{r.n_cos}</span></td>"
            f"<td>{r.ini:%d/%m}</td><td>{r.fin:%d/%m}</td><td class='n'>{r.ha:,.1f}</td>"
            f"<td class='n'><b>{f'{r.cajas:,.0f}' if r.cajas else '—'}</b></td><td class='n'>{f'{r.cajas / r.ha:,.0f}' if r.cajas and r.ha else '—'}</td></tr>"
            for r in F.itertuples())
        avance = _card("Avance de cosecha por variedad", "",
                       "<div class='scroll'><table><thead><tr><th>Variedad</th><th class='n'>Lotes</th><th>Terminados · en cosecha</th>"
                       "<th>Inicio</th><th>Último</th><th class='n'>Ha</th><th class='n'>Cajas eq.</th><th class='n'>Cajas/ha</th></tr></thead>"
                       f"<tbody>{filas}</tbody></table></div>")
    else:
        avance = None
    if avance is None:
        avance = _card("Avance de cosecha", "",
                       "<div class='scroll'><table><thead><tr><th>Lote</th><th>Variedad</th><th>Estado</th><th>Inicio</th><th>Fin</th>"
                       "<th class='n'>Días</th><th class='n'>Ha</th><th class='n'>Cajas eq.</th><th class='n'>Cajas/ha</th></tr></thead>"
                       f"<tbody>{filas}</tbody></table></div>")

    # ---- pesos: jaba, racimo, bayas y baya por grupo
    tarj = ""
    for r in F.itertuples():
        rp = cc.peso(sub("peso", r.l)) if len(sub("peso", r.l)) else None
        rj = cc.peso_jaba(sub("jabas", r.l)) if len(sub("jabas", r.l)) else None
        if not rp and not rj:
            continue
        m = lambda ico, v, u, t: (f"<div class='pm'>{ico}<div><b>{v}<small>{u}</small></b><span>{t}</span></div></div>")
        f_ = lambda x, d: "—" if x is None or pd.isna(x) else f"{x:,.{d}f}"
        tarj += (f"<div class='pz'><div class='h'><b>{escape(str(r.corto))}</b><span>{escape(str(r.var))}</span></div><div class='pms'>"
                 + m(I_JABA, f_(rj["peso"], 1) if rj else "—", "kg", "peso de jaba")
                 + m(I_RACIMO, f_(rp["peso"], 3) if rp else "—", "kg", "peso de racimo")
                 + m(I_BAYAS, f_(rp["bayas"], 0) if rp else "—", "", "bayas por racimo")
                 + m(I_BAYA, f_(rp["peso_baya_g"], 1) if rp and rp["peso_baya_g"] else "—", "g", "peso de baya")
                 + "</div></div>")
    pesos = _card("Pesos", "Promedio de la cosecha", f"<div class='pzg'>{tarj}</div>") if tarj else ""

    # ---- categoria, calibre y color (categorizacion)
    bcat, bcal, bcol, cal_cols, col_cols = "", "", "", {}, {}
    for r in F.itertuples():
        g = sub("categoria", r.l)
        rc = cc.categoria(g) if len(g) else None
        if not rc:
            continue
        cats = dict(rc["categorias"])
        partes = [("Cat 1", cats.get("Cat 1", 0) + cats.get("Cat 1 Premium", 0)), ("Cat 1.5", cats.get("Cat 1.5", 0)),
                  ("Cat 2", cats.get("Cat 2", 0)), ("Descarte", cats.get("Descarte", 0))]
        s_ = sum(v for _, v in partes) or 1
        bcat += (f"<div class='vc'><span class='top' style='color:{CAT['Cat 1']}'>{partes[0][1] / s_ * 100:.0f}%</span><div class='bar'>"
                 + "".join(f"<i class='{'dk' if n == 'Descarte' else ''}' title='{n}: {v / s_ * 100:.1f}%' style='height:{v / s_ * 100:.2f}%;"
                           f"background:{CAT[n]}'>{f'{v / s_ * 100:.0f}%' if v / s_ >= .08 else ''}</i>" for n, v in partes if v > 0)
                 + f"</div><b>{r.corto}</b><small>{r.var}</small></div>")
        cal = [(lab, v) for lab, _, v in rc["calibre"] if v > 0]
        for lab, _ in cal:
            cal_cols.setdefault(lab, PAL[len(cal_cols) % len(PAL)])
        if cal:
            dom = max(cal, key=lambda x: x[1])
            bcal += (f"<div class='hb'><span class='lb'>{r.corto}<small>{r.var}</small></span>{_st(cal, cal_cols)}"
                     f"<span class='vv'>{dom[0]}<small>{dom[1]:.0f}% calibre principal</small></span></div>")
        col = [(n, v) for n, v in rc["color"] if v > 0]
        for n, _ in col:
            col_cols[n] = BAYA.get(n, PAL[len(col_cols) % len(PAL)])
        if col:
            dom = max(col, key=lambda x: x[1])
            bcol += (f"<div class='hb'><span class='lb'>{r.corto}<small>uva {rc['tipo_color']}</small></span>"
                     f"{_st(col, col_cols, ('Full color oscuro', 'Full color claro', 'Aureola cremosa r oscuro'))}"
                     f"<span class='vv' style='font-size:.9rem'>{escape(dom[0])}<small>{dom[1]:.0f}%</small></span></div>")
    categoria = _card("Categoría por " + ("variedad" if por == "variedad" else "lote"), "% de racimos · arriba, la Categoría 1", f"<div class='vcols'>{bcat}</div>{_ley(CAT)}") if bcat else ""
    calibre = _card("Calibre por " + ("variedad" if por == "variedad" else "lote"), "", f"<div class='hbars'>{bcal}</div>{_ley(cal_cols)}") if bcal else ""
    color = _card("Color por " + ("variedad" if por == "variedad" else "lote"), "", f"<div class='hbars'>{bcol}</div>{_ley(col_cols)}") if bcol else ""

    # ---- brix: una tarjeta por lote con el inicio y el fin sobre la escala de la variedad
    bb = ""
    for r in F.itertuples():
        g = sub("brix", r.l)
        if g.empty:
            continue
        g = g[g["_fecha"] >= r.ini]
        dias_ = sorted(g["_fecha"].dt.normalize().unique())
        if not dias_:
            continue
        r0 = cc.brix(g[g["_fecha"].dt.normalize() == dias_[0]], r.var_cod)
        r1 = cc.brix(g[g["_fecha"].dt.normalize() == dias_[-1]], r.var_cod)
        if not r0 or not r1:
            continue
        tol, opt = cc.rangos_brix(r.var_cod)
        lo, hi = tol - 3, 21.0
        X = lambda x: max(0, min(100, (x - lo) / (hi - lo) * 100))
        dlt = r1["prom"] - r0["prom"]
        cd = "#3e9e62" if r1["prom"] >= opt else ("#d98e1f" if r1["prom"] >= tol else "#d9534f")
        bb += (f"<div class='bx'><div class='h'><b>{r.corto}</b><span>{r.var}</span></div>"
               f"<div class='vals'><span class='a'>{r0['prom']:.1f}°</span><span>→</span><span class='z' style='color:{cd}'>{r1['prom']:.1f}°</span>"
               f"<span class='d' style='background:{cd}22;color:{cd}'>{'+' if dlt >= 0 else ''}{dlt:.1f}°</span></div>"
               f"<div class='esc' style='--t:{X(tol):.0f}%;--o:{X(opt):.0f}%'><i class='a' style='left:{X(r0['prom']):.1f}%'></i>"
               f"<i class='z' style='left:{X(r1['prom']):.1f}%'></i></div>"
               f"<div class='pc'><span>{pd.Timestamp(dias_[0]):%d/%m} · {r0['optimo']:.0f}% óptimo</span>"
               f"<span>{pd.Timestamp(dias_[-1]):%d/%m} · {r1['optimo']:.0f}% óptimo</span></div></div>")
    brix = _card("°Brix: inicio → fin de cosecha", "○ primer día · ● último día · franja: bajo, tolerable y óptimo de la variedad",
                 f"<div class='bxg'>{bb}</div>") if bb else ""

    # ---- limpieza: tabla de calor, lotes arriba y defectos abajo
    res = []
    for r in F.itertuples():
        g = sub("limpieza", r.l)
        rl = cc.desviacion(g, "racimos-por-jaba", {}) if len(g) else None
        if rl:
            res.append((r, rl))
    res.sort(key=lambda x: -x[1]["desviacion"])
    limpieza = ""
    if res:
        tops = {}
        for _, rl in res:
            for d, p in zip(rl["detalle"]["defecto"], rl["detalle"]["pct"]):
                tops[d] = tops.get(d, 0) + p
        filas_d = [d for d, _ in sorted(tops.items(), key=lambda x: -x[1])[:8]]
        grp = {}
        for _, rl in res:
            grp.update(dict(zip(rl["detalle"]["defecto"], rl["detalle"]["grupo"])))
        mxp = max((p for _, rl in res for d, p in zip(rl["detalle"]["defecto"], rl["detalle"]["pct"]) if d in filas_d), default=1) or 1
        mxd = max(rl["desviacion"] for _, rl in res) or 1
        cel = lambda p, col, m: (f"<td class='z'>–</td>" if not p or p < 0.05 else
                                 f"<td style='background:{col}{int(25 + 200 * min(1, p / m)):02x};color:var(--fg)'>{p:.1f}%</td>")
        head = "<tr><th></th>" + "".join(f"<th>{r.corto}<small>{r.var}</small></th>" for r, _ in res) + "</tr>"
        fila_desv = ("<tr class='res'><td class='dn'>Desviación total</td>"
                     + "".join(f"<td class='tot'>{rl['desviacion']:.1f}%</td>" for _, rl in res) + "</tr>")
        fila_cal = ("<tr class='res'><td class='dn'>Calidad lograda</td>"
                    + "".join(f"<td class='cal'>{rl['calidad']:.1f}%</td>" for _, rl in res) + "</tr>")
        cuerpo = "".join(
            f"<tr><td class='dn'><i class='dot' style='background:{GC.get(grp.get(d), '#9a9290')}'></i>{escape(str(d))}</td>"
            + "".join(cel(dict(zip(rl["detalle"]["defecto"], rl["detalle"]["pct"])).get(d, 0), GC.get(grp.get(d), "#ee8f86"), mxp)
                      for _, rl in res) + "</tr>" for d in filas_d)
        limpieza = _card("Limpieza por " + ("variedad" if por == "variedad" else "lote"), "De mayor a menor desviación · los 8 defectos más frecuentes",
                         f"<div class='scroll'><table class='hm'><thead>{head}</thead><tbody>{fila_desv}{fila_cal}"
                         f"<tr><td colspan='{len(res) + 1}' class='sep'>Defectos</td></tr>{cuerpo}</tbody></table></div>{_ley(GC)}")

    fc = fecha_corte or F["fin"].max()
    head = (f"<header class='hd'><div style='display:flex;align-items:center;gap:12px'><div><div class='wm'>Pedregal</div>"
            f"<div class='tg'>the fruit company</div></div>{UVA}</div><div class='ttl'><h1>Consolidado de cosecha</h1>"
            f"<p>{escape(titulo_extra) + ' · ' if titulo_extra else ''}Campaña 2026 - 2027 · al {fc:%d/%m/%Y}</p></div>"
            f"<div class='upd'><span>Datos al</span><b>{fc:%d/%m}</b></div>"
            "</header>")
    return ("<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700&display=swap'>"
            f"<style>{CSS}</style>" + (f"<script>document.documentElement.setAttribute('data-theme','{tema}')</script>")
            + f"<div class='w'>{head}{kpis}{avance}{categoria}{brix}{pesos}{limpieza}"
            f"<div class='duo'>{calibre}{color}</div></div>")
