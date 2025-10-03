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

# ===================== Helpers =====================
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
    if st.button("Tester la connexion Sheets"):
        try:
            _, ws = _open_or_create_ws()
            st.success(f"Connexion OK → Feuille: **{SHEET_NAME}** / Onglet: **{ws.title}**")
        except Exception as e:
            st.error(f"Connexion KO : {e}")
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
        prise_8h = st.time_input("Heure prise 8h", value=None)
        dose_8h = st.selectbox("Dose matin (mg)", [10, 20, 30])
        eff_matin = st.slider("Efficacité matin (0–10)", 0, 10, 6)
        note_matin = st.text_area("Notes matin")
        effets_matin = st.text_area("Effets indésirables matin")
    with c2:
        prise_13h = st.time_input("Heure prise 13h", value=None)
        dose_13h = st.selectbox("Dose midi (mg)", [10, 20, 30])
        eff_apm = st.slider("Efficacité après-midi (0–10)", 0, 10, 6)
        note_apm = st.text_area("Notes après-midi")
        effets_apm = st.text_area("Effets indésirables après-midi")
    with c3:
        prise_16h = st.time_input("Heure prise 16h", value=None)
        dose_16h = st.selectbox("Dose après-midi (mg)", [10, 20, 30])
        eff_soir = st.slider("Efficacité soir (0–10)", 0, 10, 6)
        note_soir = st.text_area("Notes soir")
        effets_soir = st.text_area("Effets indésirables soir")

    st.subheader("💼 Travail")
    travail_debut = st.text_input("Heure début (ex: 09:00)")
    pause_dej = st.text_input("Pause déjeuner (ex: 12:30)")
    travail_aprem = st.checkbox("J'ai travaillé l'après-midi", value=True)
    reprise_aprem = st.text_input("Reprise après-midi (ex: 14:00)") if travail_aprem else ""
    fin_travail = st.text_input("Heure fin (ex: 18:30)")
    nb_patients = st.number_input("Patients vus (total)", 0, 200, 10, 1)
    nouveaux_patients = st.number_input("Nouveaux patients", 0, 200, 2, 1)

    st.subheader("🏃 Sport")
    sport = st.checkbox("J'ai fait du sport")
    type_sport = heure_sport = duree_sport = ""
    if sport:
        type_sport = st.selectbox("Type", ["Musculation","Natation","Course","Volley","Autre"])
        heure_sport = st.text_input("Heure entraînement (ex: 19:00)")
        duree_sport = st.text_input("Durée (ex: 45min / 1h15)")

    st.subheader("📌 Ressenti global")
    journee_durete = st.slider("Journée dure (0–10)", 0, 10, 4)
    commentaire = st.text_area("Commentaires libres")

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
        }  # ← FERMETURE MANQUANTE

        if (df["date"] == new["date"]).any():
            df.loc[df["date"] == new["date"], :] = pd.DataFrame([new])
        else:
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)

        target = save_data(df)
        st.success(f"✅ Données sauvegardées dans {target.upper()} ({len(df)} lignes)")