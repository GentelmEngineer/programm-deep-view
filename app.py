import os
import glob
import streamlit as st
from google import genai

# Design & Layout Setup
st.set_page_config(page_title="Programm Deep View", page_icon="⚡", layout="wide")

# CSS für den Hacker-/Terminal-Look
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !important; }
    .title-text { font-size: 2.2rem; font-weight: 700; color: #00FF66; margin-bottom: 0px; }
    .sub-text { color: #8B949E; font-size: 0.9rem; margin-bottom: 20px; }
    .stButton>button { background-color: #238636 !important; color: #ffffff !important; border: 1px solid #2EA043 !important; width: 100%; }
</style>
""", unsafe_allow_html=True)

# API-Key laden
api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("FEHLER: Der Schlüssel (GEMINI_API_KEY) fehlt noch in den Einstellungen!")
    st.stop()

# Client initialisieren
client = genai.Client(api_key=api_key)

st.markdown('<div class="title-text">> PROGRAMM_DEEP_VIEW // v1.0</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Deep-Analysis von Parteiprogrammen & Konsequenzen-Check</div>', unsafe_allow_html=True)
st.markdown("---")

# Ordner scannen
DATA_DIR = "data"
categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))] if os.path.exists(DATA_DIR) else []

st.sidebar.markdown("### [1] Wahl auswählen")
if categories:
    category_map = {c.replace("_", " ").title(): c for c in categories}
    selected_label = st.sidebar.selectbox("Kategorie:", list(category_map.keys()))
    selected_category = category_map[selected_label]
    pdf_files = glob.glob(os.path.join(DATA_DIR, selected_category, "*.pdf"))
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Gefundene Programme ({len(pdf_files)}):**")
    for pdf in pdf_files:
        st.sidebar.markdown(f"`- {os.path.basename(pdf).replace('.pdf', '')}`")
else:
    st.sidebar.error("Keine Ordner in 'data/' gefunden.")
    pdf_files = []

# Thema-Eingabe
st.markdown("### [2] Thema analysieren")
topic = st.text_input("Gib ein Thema ein (z. B. Mieten, Steuern, Digitalisierung):")

if st.button("ANALYSEN_STARTEN [ENTER]"):
    if not pdf_files:
        st.error("Keine PDFs im gewählten Ordner vorhanden!")
    elif not topic:
        st.warning("Bitte gib zuerst ein Thema ein.")
    else:
        with st.spinner("Lese Parteiprogramme und analysiere Konsequenzen..."):
            gemini_files = []
            try:
                # PDFs hochladen
                for pdf_path in pdf_files:
                    party_name = os.path.basename(pdf_path).replace(".pdf", "")
                    g_file = client.files.upload(file=pdf_path)
                    gemini_files.append((party_name, g_file))

                prompt = f"""
                Du bist ein neutraler Analyst. Vergleiche die Vorhaben der Parteien zum Thema: {topic}
                
                Antworte extrem übersichtlich im Markdown-Format:
                ## [PARTEI NAME]
                ### 1. WAS GEPLANT IST
                - Zusammenfassung der Ziele.
                ### 2. POSITIVE KONSEQUENZEN (CHANCEN)
                - Wer profitiert? Was bringt es?
                ### 3. NEGATIVE KONSEQUENZEN (RISIKEN & LÜCKEN)
                - Wo gibt es Finanzierungslücken, Kosten oder Nachteile?
                
                ---
                ## 📊 FAZIT-TABELLE
                Erstelle am Ende eine Tabelle: Partei | Hauptmaßnahme | Positiver Effekt | Hauptrisiko
                """

                # 3.5-flash-lite ist jetzt als erste Option gesetzt
                models_to_try = [
                    "gemini-2.5-flash-lite",
                    "gemini-3.5-flash",
                    "gemini-2.5-flash-lite"
                ]
                
                response = None
                last_error = None

                # Automatische Ausweich-Schleife gegen 503-Spikes
                for model_name in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=[*[f[1] for f in gemini_files], prompt]
                        )
                        if response and response.text:
                            break  # Analyse erfolgreich, Schleife beenden!
                    except Exception as err:
                        last_error = err
                        continue  # Bei Fehler direkt nächstes Modell probieren

                if response and response.text:
                    st.markdown("---")
                    st.markdown(response.text)
                else:
                    st.error(f"Fehler bei allen Modellen: {last_error}")

            except Exception as e:
                st.error(f"Allgemeiner Fehler: {e}")

            finally:
                # Aufräumen der temporären Dateien bei Google
                for _, g_file in gemini_files:
                    try:
                        client.files.delete(name=g_file.name)
                    except Exception:
                        pass
