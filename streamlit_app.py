import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import date, timedelta
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

st.set_page_config(page_title="📒 Suivi TDAH", layout="wide")

# ===================== Colonnes du journal =====================
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
        try:
            sh = GC.open(SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            sh = GC.create(SHEET_NAME)
        try:
            ws = sh.worksheet("data")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title="data", rows="1000", cols=str(len(COLUMNS)+5))
            ws.append_row(COLUMNS)
        return sh, ws

def load_data() -> pd.DataFrame:
    if USE_SHEETS:
        try:
            _, ws = _open_or_create_ws()
            data = ws.get_all_records()
            df = pd.DataFrame(data) if data else pd.DataFrame(columns=COLUMNS)
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
    df = ensure_columns(df.copy())
    if USE_SHEETS:
        try:
            sh, ws = _open_or_create_ws()
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

# ===================== Helpers (semainier) =====================
def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def week_days_for(any_day: date):
    start = week_monday(any_day)
    return [start + timedelta(days=i) for i in range(7)]

def hhmm_to_hour(hhmm: str):
    if not isinstance(hhmm, str) or not hhmm:
        return np.nan
    try:
        parts = hhmm.split(":")
        hh, mm = int(parts[0]), int(parts[1])
        return hh + mm/60.0
    except Exception:
        return np.nan

def draw_block(ax, day_idx, h_start, h_end, color, label=None, alpha=0.3):
    if any(map(np.isnan, [h_start, h_end])) or (h_end <= h_start):
        return
    x0, x1 = day_idx + 0.08, day_idx + 1 - 0.08
    rect = Rectangle((x0, h_start), x1-x0, max(0.06, h_end-h_start),
                     facecolor=color, edgecolor=color, alpha=alpha)
    ax.add_patch(rect)
    if label:
        ax.text((x0+x1)/2, (h_start+h_end)/2, label, ha="center", va="center", fontsize=9, color=color)

def draw_med(ax, day_idx, hour_val, dose):
    if np.isnan(hour_val): return
    x0, x1 = day_idx + 0.10, day_idx + 1 - 0.10
    tag_w = (x1-x0)*0.28
    ax.plot([x0, x1-tag_w-0.01], [hour_val, hour_val], color="blue", linewidth=2)
    rect = Rectangle((x1-tag_w, hour_val-0.3), tag_w, 0.6,
                     facecolor="blue", edgecolor="blue", alpha=0.95)
    ax.add_patch(rect)
    txt = f"{dose} mg" if str(dose).strip() else "dose"
    ax.text(x1-tag_w/2, hour_val, txt, color="white", fontsize=8, ha="center", va="center")

# ===================== UI =====================
st.title("📒 Suivi TDAH – Journal")

if USE_SHEETS:
    st.success("✅ Stockage : Google Sheets")
else:
    st.info("💾 Stockage : CSV local (temporaire)")

df = load_data()

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
    # Affiche immédiatement les détails quand la case est cochée
    type_sport = heure_sport = duree_sport = ""
    if sport:
        with st.container():
            csa, csb, csc = st.columns([1,1,1])
            with csa:
                type_sport = st.selectbox("Type", ["Musculation", "Natation", "Course", "Volley", "Autre"], key="type_sport")
            with csb:
                heure_sport = st.text_input("Heure entraînement (ex: 19:00)", key="heure_sport")
            with csc:
                duree_sport = st.text_input("Durée (ex: 45min / 1h15)", key="duree_sport")

    st.subheader("📌 Ressenti global")
    journee_durete = st.slider("Journée dure (0–10)", 0, 10, 4, key="durete")
    commentaire = st.text_area("Commentaires libres", key="comment")

    submitted = st.form_submit_button("💾 Enregistrer / Mettre à jour")

    if submitted:
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

# ===================== Vue semainier =====================
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
        if row.empty: continue
        row = row.iloc[0]

        def to_h(x): return hhmm_to_hour(x) if isinstance(x, str) else np.nan

        # Travail rouge
        wm, wl = to_h(row.get("travail_debut")), to_h(row.get("pause_dej"))
        last_end = np.nan
        if not np.isnan(wm) and not np.isnan(wl) and wl > wm:
            draw_block(ax, day_idx, wm, wl, "red", "Travail matin")
            last_end = wl
        if str(row.get("travail_aprem")).lower() in ["true","1","yes"]:
            wa, we = to_h(row.get("reprise_aprem")), to_h(row.get("fin_travail"))
            if not np.isnan(wa) and not np.isnan(we) and we > wa:
                draw_block(ax, day_idx, wa, we, "red", "Travail AM")
                last_end = max(last_end, we) if not np.isnan(last_end) else we
        try:
            if not np.isnan(last_end):
                pts = int(float(row.get("nb_patients") or 0))
                ax.text(day_idx+0.06, min(23.6, last_end+0.6), f"👥 {pts} patients", fontsize=9, va="bottom")
        except: pass

        # Sport vert
        if str(row.get("sport")).lower() in ["true","1","yes"]:
            starth = to_h(row.get("heure_sport"))
            dur = 1.0
            ds = str(row.get("duree_sport") or "").lower()
            if "h" in ds or "min" in ds:
                try:
                    hh, mm = 0, 0
                    if "h" in ds: hh = int(ds.split("h")[0].strip())
                    if "min" in ds: mm = int(ds.split("min")[0].strip())
                    dur = hh + mm/60
                except: pass
            if not np.isnan(starth):
                draw_block(ax, day_idx, starth, starth+dur, "green", row.get("type_sport","sport"))

        # Prises bleues
        for tcol, dcol in [("prise_8h","dose_8h"),("prise_13h","dose_13h"),("prise_16h","dose_16h")]:
            hv = hhmm_to_hour(row.get(tcol)) if isinstance(row.get(tcol), str) else np.nan
            draw_med(ax, day_idx, hv, row.get(dcol))

        # Notes brèves
        def cartouche(text, center_hour):
            if not isinstance(text, str) or not text.strip(): return
            x0, x1 = day_idx+0.14, day_idx+1-0.14
            h = 0.9; y = center_hour - h/2
            rect = Rectangle((x0, y), x1-x0, h, facecolor="white", edgecolor="black", linewidth=0.7, alpha=0.9)
            ax.add_patch(rect)
            ax.text((x0+x1)/2, center_hour, text[:140]+("…" if len(text)>140 else ""),
                    ha="center", va="center", fontsize=8)
        cartouche(str(row.get("note_matin") or ""), 10.5)
        cartouche(str(row.get("note_apresmidi") or ""), 15.0)
        cartouche(str(row.get("note_soir") or ""), 20.5)

    return fig

pick = st.date_input("Choisir une date (affiche sa semaine)", value=date.today(), key="weekpick")
if isinstance(pick, list) and pick: pick = pick[0]
fig = build_week_plot(df, pick)
st.pyplot(fig)

st.markdown("---")
st.subheader("📊 Données enregistrées")
st.dataframe(df.sort_values("date"))
