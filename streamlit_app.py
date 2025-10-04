import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import date, timedelta
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

st.set_page_config(page_title="📒 Suivi TDAH", layout="wide")

# ===================== Schéma de données =====================
COLUMNS = [
    "date",
    "heure_couche", "duree_sommeil",
    "prise_8h", "dose_8h", "efficacite_matin", "note_matin", "effets_matin",
    "prise_13h", "dose_13h", "efficacite_apresmidi", "note_apresmidi", "effets_apresmidi",
    "prise_16h", "dose_16h", "efficacite_soir", "note_soir", "effets_soir",
    "travail_debut", "pause_dej", "travail_aprem", "reprise_aprem", "fin_travail",
    "nb_patients", "nouveaux_patients",
    "sport", "type_sport", "heure_sport", "duree_sport",
    "journee_durete", "commentaire",
]

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
CSV_PATH = os.path.join(DATA_DIR, "journal.csv")

def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    # types simples utiles
    for col in ["nb_patients","nouveaux_patients","dose_8h","dose_13h","dose_16h",
                "efficacite_matin","efficacite_apresmidi","efficacite_soir","journee_durete"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[COLUMNS]

# ===================== Google Sheets (si dispo) =====================
USE_SHEETS = ("gcp_service_account" in st.secrets) and ("sheets" in st.secrets)

if USE_SHEETS:
    import gspread
    from google.oauth2.service_account import Credentials

    SCOPE = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    CREDS = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPE
    )
    GC = gspread.authorize(CREDS)
    SHEET_NAME = st.secrets["sheets"].get("sheet_name", "Journal TDAH")

    def _open_or_create_ws():
        """Ouvre la feuille et l’onglet data; crée si nécessaire."""
        try:
            sh = GC.open(SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            sh = GC.create(SHEET_NAME)
        try:
            ws = sh.worksheet("data")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title="data", rows="2000", cols=str(len(COLUMNS) + 8))
            ws.append_row(COLUMNS)
        return sh, ws

def load_data() -> pd.DataFrame:
    if USE_SHEETS:
        try:
            _, ws = _open_or_create_ws()
            records = ws.get_all_records()
            df = pd.DataFrame(records) if records else pd.DataFrame(columns=COLUMNS)
            return ensure_columns(df)
        except Exception as e:
            st.warning(f"⚠️ Google Sheets indisponible ({e}). Passage en CSV local.")
    # Fallback CSV
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
        except Exception:
            df = pd.DataFrame(columns=COLUMNS)
    else:
        df = pd.DataFrame(columns=COLUMNS)
    return ensure_columns(df)

def save_data(df: pd.DataFrame) -> str:
    """Sauve et retourne 'sheets' ou 'csv'."""
    df = ensure_columns(df.copy())
    if USE_SHEETS:
        try:
            _, ws = _open_or_create_ws()
            ws.clear()
            ws.append_row(COLUMNS)
            if not df.empty:
                values = df.fillna("").astype(str).values.tolist()
                ws.append_rows(values)
            return "sheets"
        except Exception as e:
            st.error(f"Erreur écriture Google Sheets : {e}. Données sauvegardées en CSV local.")
    df.to_csv(CSV_PATH, index=False)
    return "csv"

# ===================== Helpers =====================
def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def week_days_for(any_day: date):
    start = week_monday(any_day)
    return [start + timedelta(days=i) for i in range(7)]

def hhmm_to_hour(hhmm: str):
    """'08:30' -> 8.5 ; '' -> nan"""
    if not isinstance(hhmm, str) or not hhmm:
        return np.nan
    try:
        parts = hhmm.split(":")
        hh, mm = int(parts[0]), int(parts[1])
        return hh + mm / 60.0
    except Exception:
        return np.nan

def parse_duration_hmin(txt: str):
    """'7h45' -> 7.75 ; '45min' -> 0.75 ; '' -> nan"""
    if not isinstance(txt, str) or not txt.strip():
        return np.nan
    s = txt.lower().replace(" ", "")
    try:
        if "h" in s:
            hh = int(s.split("h")[0] or 0)
            mm_part = s.split("h")[1]
            mm = int(mm_part.replace("min","") or 0) if "min" in mm_part else 0
            return hh + mm/60
        if "min" in s:
            mm = int(s.replace("min",""))
            return mm/60
    except Exception:
        return np.nan
    return np.nan

def hours_worked(row):
    """Heures travaillées = (pause_dej - debut) + (fin - reprise) si aprem travaillé."""
    m1 = hhmm_to_hour(row.get("travail_debut"))
    m2 = hhmm_to_hour(row.get("pause_dej"))
    a1 = hhmm_to_hour(row.get("reprise_aprem"))
    a2 = hhmm_to_hour(row.get("fin_travail"))
    total = 0.0
    if not np.isnan(m1) and not np.isnan(m2) and m2 > m1:
        total += (m2 - m1)
    if str(row.get("travail_aprem")).lower() in ["true","1","yes"]:
        if not np.isnan(a1) and not np.isnan(a2) and a2 > a1:
            total += (a2 - a1)
    return total if total > 0 else np.nan

def avg_efficacy(row):
    vals = [row.get("efficacite_matin"), row.get("efficacite_apresmidi"), row.get("efficacite_soir")]
    vals = [v for v in vals if pd.notnull(v)]
    return float(np.mean(vals)) if vals else np.nan

def draw_block(ax, day_idx, h_start, h_end, color, label=None, alpha=0.3):
    if any(map(np.isnan, [h_start, h_end])) or (h_end <= h_start):
        return
    x0, x1 = day_idx + 0.08, day_idx + 1 - 0.08
    rect = Rectangle((x0, h_start), x1 - x0, max(0.06, h_end - h_start),
                     facecolor=color, edgecolor=color, alpha=alpha)
    ax.add_patch(rect)
    if label:
        ax.text((x0 + x1) / 2, (h_start + h_end) / 2, label,
                ha="center", va="center", fontsize=9, color=color)

def draw_med(ax, day_idx, hour_val, dose):
    if np.isnan(hour_val):
        return
    x0, x1 = day_idx + 0.10, day_idx + 1 - 0.10
    tag_w = (x1 - x0) * 0.28
    ax.plot([x0, x1 - tag_w - 0.01], [hour_val, hour_val], color="blue", linewidth=2)
    rect = Rectangle((x1 - tag_w, hour_val - 0.3), tag_w, 0.6,
                     facecolor="blue", edgecolor="blue", alpha=0.95)
    ax.add_patch(rect)
    txt = f"{dose} mg" if str(dose).strip() else "dose"
    ax.text(x1 - tag_w / 2, hour_val, txt, color="white", fontsize=8, ha="center", va="center")

# ===================== UI Header =====================
st.title("📒 Suivi TDAH – Journal")

top1, top2 = st.columns([1, 1])
with top1:
    if USE_SHEETS:
        st.success("✅ Stockage : Google Sheets")
    else:
        st.info("💾 Stockage : CSV local (temporaire)")
with top2:
    if USE_SHEETS and st.button("Tester la connexion Sheets"):
        try:
            sh, ws = _open_or_create_ws()
            st.success(f"Connexion OK → Feuille: **{SHEET_NAME}** / Onglet: **{ws.title}**")
        except Exception as e:
            st.error(f"Connexion KO : {e}")

df = load_data()

# --------------------- Formulaire ---------------------
with st.form("journal_form"):
    d = st.date_input("Date", value=date.today())

    st.subheader("😴 Sommeil")
    heure_couche = st.text_input("Heure de couché (ex: 23:30)")
    duree_sommeil = st.text_input("Durée du sommeil (ex: 7h45)")

    st.subheader("💊 Prises du traitement")
    c1, c2, c3 = st.columns(3)
    with c1:
        prise_8h = st.time_input("Heure prise 8h", value=None, key="p8")
        dose_8h = st.selectbox("Dose matin (mg)", [10, 20, 30], key="d8")
        eff_matin = st.slider("Efficacité matin (0–10)", 0, 10, 6, key="e_matin")
        note_matin = st.text_area("Notes matin", key="n_matin")
        effets_matin = st.text_area("Effets indésirables matin", key="ei_matin")
    with c2:
        prise_13h = st.time_input("Heure prise 13h", value=None, key="p13")
        dose_13h = st.selectbox("Dose midi (mg)", [10, 20, 30], index=1, key="d13")
        eff_apm = st.slider("Efficacité après-midi (0–10)", 0, 10, 6, key="e_apm")
        note_apm = st.text_area("Notes après-midi", key="n_apm")
        effets_apm = st.text_area("Effets indésirables après-midi", key="ei_apm")
    with c3:
        prise_16h = st.time_input("Heure prise 16h", value=None, key="p16")
        dose_16h = st.selectbox("Dose après-midi (mg)", [10, 20, 30], key="d16")
        eff_soir = st.slider("Efficacité soir (0–10)", 0, 10, 6, key="e_soir")
        note_soir = st.text_area("Notes soir", key="n_soir")
        effets_soir = st.text_area("Effets indésirables soir", key="ei_soir")

    st.subheader("💼 Travail")
    travail_debut = st.text_input("Heure début (ex: 09:00)")
    pause_dej = st.text_input("Pause déjeuner (ex: 12:30)")
    travail_aprem = st.checkbox("J'ai travaillé l'après-midi", value=True, key="t_apm")
    reprise_aprem = st.text_input("Reprise après-midi (ex: 14:00)") if travail_aprem else ""
    fin_travail = st.text_input("Heure fin (ex: 18:30)")
    nb_patients = st.number_input("Patients vus (total)", 0, 200, 0, 1)
    nouveaux_patients = st.number_input("Nouveaux patients", 0, 200, 0, 1)

    st.subheader("🏃 Sport")
    sport = st.checkbox("J'ai fait du sport", key="sport_chk")
    # Détails sport : TOUJOURS visibles, simplement désactivés si non cochés
    type_sport = st.selectbox(
        "Type de sport", ["Musculation", "Natation", "Course", "Volley", "Autre"],
        key="type_sport", disabled=not sport
    )
    heure_sport = st.text_input(
        "Heure de l'entraînement (ex: 19:00)", key="heure_sport", disabled=not sport
    )
    duree_sport = st.text_input(
        "Durée (ex: 45min / 1h15)", key="duree_sport", disabled=not sport
    )

    st.subheader("📌 Ressenti global")
    journee_durete = st.slider("Journée dure (0–10)", 0, 10, 4, key="durete")
    commentaire = st.text_area("Commentaires libres", key="comment")

    submitted = st.form_submit_button("💾 Enregistrer / Mettre à jour")

    if submitted:
        if not sport:
            type_sport, heure_sport, duree_sport = "", "", ""
        new = {
            "date": str(d),
            "heure_couche": heure_couche, "duree_sommeil": duree_sommeil,
            "prise_8h": str(prise_8h) if prise_8h else "", "dose_8h": int(dose_8h),
            "efficacite_matin": int(eff_matin), "note_matin": note_matin, "effets_matin": effets_matin,
            "prise_13h": str(prise_13h) if prise_13h else "", "dose_13h": int(dose_13h),
            "efficacite_apresmidi": int(eff_apm), "note_apresmidi": note_apm, "effets_apresmidi": effets_apm,
            "prise_16h": str(prise_16h) if prise_16h else "", "dose_16h": int(dose_16h),
            "efficacite_soir": int(eff_soir), "note_soir": note_soir, "effets_soir": effets_soir,
            "travail_debut": travail_debut, "pause_dej": pause_dej, "travail_aprem": bool(travail_aprem),
            "reprise_aprem": reprise_aprem, "fin_travail": fin_travail,
            "nb_patients": int(nb_patients), "nouveaux_patients": int(nouveaux_patients),
            "sport": bool(sport), "type_sport": type_sport, "heure_sport": heure_sport, "duree_sport": duree_sport,
            "journee_durete": int(journee_durete), "commentaire": commentaire
        }
        if (df["date"] == new["date"]).any():
            df.loc[df["date"] == new["date"], :] = pd.DataFrame([new])
        else:
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
        target = save_data(df)
        st.success(f"✅ Données sauvegardées dans {target.upper()} ({len(df)} lignes)")

# --------------------- Vue semainier ---------------------
st.markdown("---")
st.subheader("🗓️ Vue semainier (6h → 24h)")

def build_week_plot(df: pd.DataFrame, pick: date):
    days = week_days_for(pick)
    labels = [d.strftime("%a %d/%m") for d in days]
    week_dates = [str(d) for d in days]
    wdf = df[df["date"].isin(week_dates)].copy().sort_values("date")

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 7); ax.set_ylim(6, 24); ax.invert_yaxis()
    ax.set_xticks([i + 0.5 for i in range(7)]); ax.set_xticklabels(labels)
    ax.set_yticks(range(6, 25, 2)); ax.set_yticklabels([f"{h:02d}:00" for h in range(6, 25, 2)])
    for x in range(8): ax.axvline(x, linestyle="--", alpha=0.25)
    for y in range(6, 25): ax.axhline(y, linestyle=":", alpha=0.07)
    ax.set_title(f"Semaine du {days[0].strftime('%d/%m/%Y')} au {days[-1].strftime('%d/%m/%Y')}")

    for day_idx, the_day in enumerate(days):
        row = wdf[wdf["date"] == str(the_day)]
        if row.empty: 
            continue
        row = row.iloc[0]

        def to_h(x): return hhmm_to_hour(x) if isinstance(x, str) else np.nan

        # Travail rouge
        wm, wl = to_h(row.get("travail_debut")), to_h(row.get("pause_dej"))
        last_end = np.nan
        if not np.isnan(wm) and not np.isnan(wl) and wl > wm:
            draw_block(ax, day_idx, wm, wl, "red", "Travail matin")
            last_end = wl
        if str(row.get("travail_aprem")).lower() in ["true", "1", "yes"]:
            wa, we = to_h(row.get("reprise_aprem")), to_h(row.get("fin_travail"))
            if not np.isnan(wa) and not np.isnan(we) and we > wa:
                draw_block(ax, day_idx, wa, we, "red", "Travail AM")
                last_end = max(last_end, we) if not np.isnan(last_end) else we
        # Patients sous le dernier bloc
        try:
            if not np.isnan(last_end):
                pts = int(float(row.get("nb_patients") or 0))
                news = int(float(row.get("nouveaux_patients") or 0))
                ax.text(day_idx + 0.06, min(23.0, last_end + 0.6),
                        f"👥 {pts} (nouveaux: {news})", fontsize=9, va="bottom")
        except:
            pass

        # Sport vert
        if str(row.get("sport")).lower() in ["true", "1", "yes"]:
            starth = to_h(row.get("heure_sport"))
            dur = 1.0
            ds = str(row.get("duree_sport") or "").lower()
            if "h" in ds or "min" in ds:
                try:
                    hh, mm = 0, 0
                    if "h" in ds:
                        hh = int(ds.split("h")[0].strip())
                        rest = ds.split("h")[1]
                        if "min" in rest:
                            mm = int(rest.split("min")[0].strip())
                    elif "min" in ds:
                        mm = int(ds.split("min")[0].strip())
                    dur = hh + mm / 60
                except:
                    pass
            if not np.isnan(starth):
                label = row.get("type_sport","sport")
                if isinstance(label,str) and len(label)>14: label = label[:14]+"…"
                draw_block(ax, day_idx, starth, starth + dur, "green", label)

        # Prises bleues
        for tcol, dcol in [("prise_8h", "dose_8h"), ("prise_13h", "dose_13h"), ("prise_16h", "dose_16h")]:
            hv = hhmm_to_hour(row.get(tcol)) if isinstance(row.get(tcol), str) else np.nan
            draw_med(ax, day_idx, hv, row.get(dcol))

        # Bandeau récap en BAS de la journée (infos demandées)
        # Sommeil
        sleep_h = parse_duration_hmin(row.get("duree_sommeil"))
        sleep_txt = f"😴 {row.get('duree_sommeil')}" if pd.notnull(sleep_h) else "😴 n/d"
        # Heures travaillées
        hw = hours_worked(row)
        hw_txt = f"⏱️ {hw:.1f} h" if pd.notnull(hw) else "⏱️ 0 h"
        # Dureté
        d_txt = f"💪 {int(row.get('journee_durete'))}/10" if pd.notnull(row.get("journee_durete")) else "💪 n/d"
        # EI (concat court)
        ei = " | ".join([str(row.get("effets_matin") or ""), str(row.get("effets_apresmidi") or ""), str(row.get("effets_soir") or "")]).strip()
        ei = ei.replace("  "," ").strip(" |")
        if len(ei) > 40: ei = ei[:40] + "…"
        ei_txt = f"⚠️ {ei}" if ei else "⚠️ —"
        # Commentaire court
        com = str(row.get("commentaire") or "").strip()
        if len(com) > 50: com = com[:50] + "…"
        com_txt = f"📝 {com}" if com else "📝 —"

        base_y = 23.8
        ax.text(day_idx + 0.06, base_y, sleep_txt + "   " + hw_txt + "   " + d_txt,
                fontsize=8, va="top")
        ax.text(day_idx + 0.06, base_y - 0.45, ei_txt, fontsize=8, va="top")
        ax.text(day_idx + 0.06, base_y - 0.90, com_txt, fontsize=8, va="top")

    return fig

pick = st.date_input("Choisir une date (affiche sa semaine)", value=date.today(), key="weekpick")
if isinstance(pick, list) and pick:
    pick = pick[0]
fig = build_week_plot(df, pick)
st.pyplot(fig)

# --------------------- Analyse & Corrélations ---------------------
st.markdown("---")
st.subheader("📈 Analyse & corrélations")

# Période d'analyse
col_a, col_b = st.columns(2)
with col_a:
    days_range = st.slider("Période d'analyse (jours en arrière)", 7, 90, 21)
with col_b:
    st.caption("Astuce : remplis régulièrement les 3 efficacités (matin/apm/soir) pour une moyenne fiable.")

if not df.empty:
    # Prépare un DF métriques
    dfa = df.copy()
    dfa["date"] = pd.to_datetime(dfa["date"], errors="coerce")
    dfa = dfa.sort_values("date").dropna(subset=["date"])
    since = date.today() - timedelta(days=days_range)
    dfa = dfa[dfa["date"] >= pd.to_datetime(since)]

    dfa["sleep_h"] = dfa["duree_sommeil"].apply(parse_duration_hmin)
    dfa["work_h"] = dfa.apply(hours_worked, axis=1)
    dfa["eff_avg"] = dfa.apply(avg_efficacy, axis=1)

    # Tableau résumé
    st.markdown("**Variables suivies (période sélectionnée)**")
    view_cols = ["date","sleep_h","work_h","nb_patients","nouveaux_patients","eff_avg","journee_durete"]
    st.dataframe(dfa[view_cols].round(2))

    # Corrélations (Pearson r via numpy)
    def corr_pair(x, y):
        x = pd.to_numeric(x, errors="coerce")
        y = pd.to_numeric(y, errors="coerce")
        m = x.notna() & y.notna()
        if m.sum() < 3:  # trop peu de points
            return np.nan
        return np.corrcoef(x[m], y[m])[0,1]

    corr_data = {
        "Heures travaillées ↔ Efficacité": corr_pair(dfa["work_h"], dfa["eff_avg"]),
        "Patients (total) ↔ Efficacité": corr_pair(dfa["nb_patients"], dfa["eff_avg"]),
        "Nouveaux patients ↔ Efficacité": corr_pair(dfa["nouveaux_patients"], dfa["eff_avg"]),
        "Sommeil (h) ↔ Efficacité": corr_pair(dfa["sleep_h"], dfa["eff_avg"]),
        "Dureté ↔ Efficacité": corr_pair(dfa["journee_durete"], dfa["eff_avg"]),
    }
    corr_df = pd.DataFrame(
        [{"Relation": k, "r (≈ force & signe)": (f"{v:.2f}" if pd.notnull(v) else "n/d")} for k,v in corr_data.items()]
    )
    st.markdown("**Corrélations (r de Pearson)**  \n> proche de **-1** : forte relation inverse • proche de **+1** : forte relation directe • **0** : pas de lien linéaire")
    st.dataframe(corr_df, use_container_width=True)

    # Scatter + droite de régression
    def scatter_with_fit(x, y, xlabel, ylabel, title):
        x = pd.to_numeric(x, errors="coerce")
        y = pd.to_numeric(y, errors="coerce")
        m = x.notna() & y.notna()
        if m.sum() < 3:
            st.info(f"Pas assez de points pour le graphique « {title} ».")
            return
        xv, yv = x[m].values, y[m].values
        # droite de régression y = a x + b
        a, b = np.polyfit(xv, yv, 1)
        r = np.corrcoef(xv, yv)[0,1]

        fig2, ax2 = plt.subplots(figsize=(5.5, 4))
        ax2.scatter(xv, yv)
        xs = np.linspace(xv.min(), xv.max(), 50)
        ax2.plot(xs, a*xs + b)
        ax2.set_xlabel(xlabel); ax2.set_ylabel(ylabel)
        ax2.set_title(f"{title}\nr = {r:.2f}")
        st.pyplot(fig2)

    c1, c2, c3 = st.columns(3)
    with c1:
        scatter_with_fit(dfa["work_h"], dfa["eff_avg"], "Heures travaillées", "Efficacité moyenne (0-10)", "Travail ↔ Efficacité")
    with c2:
        scatter_with_fit(dfa["nb_patients"], dfa["eff_avg"], "Patients (total)", "Efficacité moyenne (0-10)", "Patients ↔ Efficacité")
    with c3:
        scatter_with_fit(dfa["sleep_h"], dfa["eff_avg"], "Sommeil (h)", "Efficacité moyenne (0-10)", "Sommeil ↔ Efficacité")

    # Interprétation rapide
    st.markdown("**Lecture rapide :**")
    bullets = []
    r_work = corr_data["Heures travaillées ↔ Efficacité"]
    if pd.notnull(r_work):
        if r_work <= -0.3: bullets.append("Quand **l'amplitude/charge de travail augmente**, l'**efficacité ressentie baisse** (effet fatigue/surcharge possible).")
        elif r_work >= 0.3: bullets.append("Plus tu **travailles**, plus l'**efficacité ressentie monte** (effet d’activation/flow ?).")
    r_sleep = corr_data["Sommeil (h) ↔ Efficacité"]
    if pd.notnull(r_sleep):
        if r_sleep >= 0.3: bullets.append("Plus tu **dors**, meilleure est l’**efficacité** (le sommeil soutient le traitement).")
        elif r_sleep <= -0.3: bullets.append("Plus tu **dors**, plus l’**efficacité baisse** (peut refléter des nuits très longues non réparatrices).")
    r_pat = corr_data["Patients (total) ↔ Efficacité"]
    if pd.notnull(r_pat):
        if r_pat <= -0.3: bullets.append("Plus il y a de **patients**, plus l’**efficacité baisse** (charge cognitive).")
        elif r_pat >= 0.3: bullets.append("Plus de **patients** s’accompagnent d’**efficacité** plus haute (stimulation).")
    if not bullets:
        bullets.append("Aucun lien linéaire net — poursuis le suivi quelques semaines pour y voir plus clair.")
    for b in bullets: st.write("• " + b)
else:
    st.info("Pas encore de données pour analyser les corrélations.")

st.markdown("---")
st.subheader("📊 Données enregistrées")
st.dataframe(df.sort_values("date"))
