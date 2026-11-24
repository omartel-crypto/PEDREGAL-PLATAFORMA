"""Convierte los codigos de lote/cuartel que vienen en las tablas al codigo del mapa
(FUNDO.LOTE.CUARTEL). No depende de Streamlit, para poder probarlo solo."""
import re
import unicodedata


def compacto(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", x)


class UnionMapa:
    def __init__(self, features):
        self.cuarteles = {}            # compacto -> cuartel_id
        self.lotes = {}                # compacto -> lote_id
        self.lote_por_num = {}         # 24 -> YAURILLA.L24
        self.cu_de_lote = {}           # lote_id -> {compacto(cuartel): cuartel_id}
        self.fundos = set()
        for f in features:
            p = f["properties"]
            self.cuarteles[compacto(p["cuartel_id"])] = p["cuartel_id"]
            self.lotes[compacto(p["lote_id"])] = p["lote_id"]
            self.lote_por_num[int(p["lote"][1:])] = p["lote_id"]
            self.cu_de_lote.setdefault(p["lote_id"], {})[compacto(p["cuartel"]).lstrip("0") or "0"] = p["cuartel_id"]
            self.fundos.add(compacto(p["fundo"]))

    def resolver(self, valor):
        """Devuelve (lote_id, cuartel_id o None). (None, None) si no se reconoce."""
        if valor is None:
            return None, None
        c = compacto(valor)
        if not c:
            return None, None
        if c in self.cuarteles:
            cid = self.cuarteles[c]
            return cid.rsplit(".", 1)[0], cid
        if c in self.lotes:
            return self.lotes[c], None
        txt = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode().upper()
        tokens = re.findall(r"\d+|[A-Z]+", txt)
        idx = next((i for i, t in enumerate(tokens) if t.isdigit()), None)
        if idx is None:
            return None, None
        num = tokens[idx]
        lote = self.lote_por_num.get(int(num))
        if lote:
            # lo que sigue al numero de lote es el cuartel ("L24-01", "L61 A", "L24.C01")
            cola = "".join(tokens[idx + 1:])
            cola = re.sub(r"^(?:CUARTEL|CU|C|Q)(?=\d)", "", cola)
            if not cola:
                return lote, None
            return lote, self.cu_de_lote[lote].get(cola.lstrip("0") or "0")
        # numero pegado sin separador, p.ej. "2401" o "7129" = lote + cuartel
        for k in (2, 1):
            if len(num) > k:
                l2 = self.lote_por_num.get(int(num[:k]))
                if l2:
                    cu = self.cu_de_lote[l2].get(num[k:].lstrip("0") or "0")
                    if cu:
                        return l2, cu
        return None, None
