import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="📒 Suivi TDAH", layout="wide")

# Colonnes du journal
COLUMNS = [
    "date",
    "heure_couche", "duree_sommeil",
    "prise_8h", "dose_8h", "efficacite_matin", "note_matin", "effets_matin",
    "prise_13h", "dose_13h", "efficacite_apresmidi", "note_apresmidi", "effets_apresmidi",
    "prise_16h", "dose_16h", "efficacite_soir", "note_soir", "effets_soir",
    "travail_debut", "pause_dej", "travail_aprem", "reprise_aprem", "fin_travail",
    "nb_patients", "nouveaux_patients",
    "sport", "type_sport", "heure_sport", "duree_sport",
    "journee_durete", "commentaire"
]

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
CSV_PATH = os.path.join(DATA_DIR, "journal.csv")

def load_data():
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
        except Exception:
            df = pd.DataFrame(columns=COLUMNS)
    else:
        df = pd.DataFrame(columns=COLUMNS)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    return df

def save_data(df):
    df.to_csv(CSV_PATH, index=False)

df = load_data()

st.title("📒 Suivi TDAH – Journal")

with st.form("journal_form"):
    date = st.date_input("Date")

    st.subheader("😴 Sommeil")
    heure_couche = st.text_input("Heure de couché (ex: 23h30)")
    duree_sommeil = st.text_input("Durée du sommeil (ex: 7h45)")

    st.subheader("💊 Prises du traitement")
    col1, col2, col3 = st.columns(3)
    with col1:
        prise_8h = st.time_input("Heure de prise matin (8h)", value=None)
        dose_8h = st.selectbox("Dose matin", [10, 20, 30])
        efficacite_matin = st.slider("Efficacité matin (0-10)", 0, 10, 5)
        note_matin = st.text_area("Notes matin")
        effets_matin = st.text_area("Effets indésirables matin")
    with col2:
        prise_13h = st.time_input("Heure de prise midi (13h)", value=None)
        dose_13h = st.selectbox("Dose midi", [10, 20, 30])
        efficacite_apresmidi = st.slider("Efficacité après-midi (0-10)", 0, 10, 5)
        note_apresmidi = st.text_area("Notes après-midi")
        effets_apresmidi = st.text_area("Effets indésirables après-midi")
    with col3:
        prise_16h = st.time_input("Heure de prise après-midi (16h)", value=None)
        dose_16h = st.selectbox("Dose après-midi", [10, 20, 30])
        efficacite_soir = st.slider("Efficacité soir (0-10)", 0, 10, 5)
        note_soir = st.text_area("Notes soir")
        effets_soir = st.text_area("Effets indésirables soir")

    st.subheader("💼 Travail")
    travail_debut = st.text_input("Heure début travail (ex: 9h00)")
    pause_dej = st.text_input("Heure pause déjeuner (ex: 12h30)")
    travail_aprem = st.checkbox("J'ai travaillé l'après-midi")
    reprise_aprem = ""
    if travail_aprem:
        reprise_aprem = st.text_input("Heure reprise après-midi (ex: 14h00)")
    fin_travail = st.text_input("Heure fin travail (ex: 18h30)")
    nb_patients = st.number_input("Nombre total de patients vus", min_value=0, step=1)
    nouveaux_patients = st.number_input("Nombre de nouveaux patients", min_value=0, step=1)

    st.subheader("🏋️ Sport")
    sport = st.checkbox("J'ai fait du sport")
    type_sport = heure_sport = duree_sport = ""
    if sport:
        type_sport = st.selectbox("Type de sport", ["Musculation", "Natation", "Course", "Volley", "Autre"])
        heure_sport = st.text_input("Heure de l'entraînement (ex: 19h)")
        duree_sport = st.text_input("Durée (ex: 1h15)")

    st.subheader("📌 Impressions générales")
    journee_durete = st.slider("La journée était dure (0-10)", 0, 10, 5)
    commentaire = st.text_area("Commentaires libres (soir, résumé, etc.)")

    submitted = st.form_submit_button("💾 Enregistrer / Mettre à jour")

    if submitted:
        new_row = {
            "date": date,
            "heure_couche": heure_couche, "duree_sommeil": duree_sommeil,
            "prise_8h": prise_8h, "dose_8h": dose_8h, "efficacite_matin": efficacite_matin, "note_matin": note_matin, "effets_matin": effets_matin,
            "prise_13h": prise_13h, "dose_13h": dose_13h, "efficacite_apresmidi": efficacite_apresmidi, "note_apresmidi": note_apresmidi, "effets_apresmidi": effets_apresmidi,
            "prise_16h": prise_16h, "dose_16h": dose_16h, "efficacite_soir": efficacite_soir, "note_soir": note_soir, "effets_soir": effets_soir,
            "travail_debut": travail_debut, "pause_dej": pause_dej, "travail_aprem": travail_aprem, "reprise_aprem": reprise_aprem, "fin_travail": fin_travail,
            "nb_patients": nb_patients, "nouveaux_patients": nouveaux_patients,
            "sport": sport, "type_sport": type_sport, "heure_sport": heure_sport, "duree_sport": duree_sport,
            "journee_durete": journee_durete, "commentaire": commentaire
        }

        if (df["date"] == str(date)).any():
            df.loc[df["date"] == str(date), :] = pd.DataFrame([new_row])
        else:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_data(df)
        st.success("✅ Données sauvegardées")

st.subheader("📊 Données enregistrées")
if not df.empty:
    st.dataframe(df)
else:
    st.info("Aucune donnée enregistrée pour le moment.")
