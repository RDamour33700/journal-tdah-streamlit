import streamlit as st, os

st.set_page_config(page_title="Test déploiement", layout="wide")
st.title("✅ Déploiement OK")
st.write("Si tu lis ceci depuis Streamlit Cloud, le fichier `streamlit_app.py` a été trouvé.")

st.subheader("Debug rapide")
st.write("Répertoire courant:", os.getcwd())
st.write("Fichiers présents:", os.listdir("."))
