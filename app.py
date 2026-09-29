import os
import glob
import time
import streamlit as st
from google import genai
from google.genai import types

# ---------------------------------------------------------
# Design & Layout Setup
# ---------------------------------------------------------
st.set_page_config(page_title="Programm Deep View", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !important; }
    .title-text { font-size: 2.2rem; font-weight: 700; color: #00FF66; margin-bottom: 0px; }
    .sub-text { color: #8B949E; font-size: 0.9rem; margin-bottom: 20px; }
    .stButton>button { background-color: #238636 !important; color: #ffffff !important; border: 1px solid #2EA043 !important; width: 100%; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# API-Key & Client mit Retry-Strategie initialisieren
# ---------------------------------------------------------
api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("FEHLER: Der Schlüssel (GEMINI_API_KEY) fehlt noch in den Einstellungen!")
    st.stop()

# Client mit automatischer Retry-Konfiguration für 503/Spikes erstellen
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=5,        # 5 automatische Neuversuche bei 503/429
            backoff_factor=2   # Exponentielle Wartezeit zwischen den Versuchen (2s, 4s, 8s...)
        )
    )
)

st.markdown('<div class="title-text">> PROGRAMM_DEEP_VIEW // v1.0</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Deep-Analysis von Parteiprogrammen & Konsequenzen-Check</div>', unsafe_allow_html=True)
st.markdown("---")

# ---------------------------------------------------------
# Ordner & PDF-Scandateien
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# Hauptlogik: Prompt & Multi-Model-Fallback
# ---------------------------------------------------------
st.markdown("### [2] Thema analysieren")
topic = st.text_input("Gib ein Thema ein (z. B. Mieten, Steuern, Digitalisierung):")

if st.button("ANALYSEN_STARTEN [ENTER]"):
    if not pdf_files:
        st.error("Keine PDFs im gewählten Ordner vorhanden!")
    elif not topic:
        st.warning("Bitte gib zuerst ein Thema ein.")
    else:
        with st.spinner("Lese Parteiprogramme und erstelle Analyse..."):
            gemini_files = []
            try:
                # 1. PDFs temporär hochladen
                for pdf_path in pdf_files:
                    party_name = os.path.basename(pdf_path).replace(".pdf", "")
                    g_file = client.files.upload(file=pdf_path)
                    gemini_files.append((party_name, g_file))

                # 2. Prompt aufbauen
                prompt = f"""
                Du bist ein neutraler Politikanalyst. Vergleiche die Vorhaben der Parteien zum Thema: {topic}
                
                Antworte extrem übersichtlich im Markdown-Format:
                ## [PARTEI NAME]
                ### 1. WAS GEPLANT IST
                - Zusammenfassung der konkreten Ziele.
                ### 2. POSITIVE KONSEQUENZEN (CHANCEN)
                - Wer profitiert? Was sind die Vorteile?
                ### 3. NEGATIVE KONSEQUENZEN (RISIKEN & LÜCKEN)
                - Wo gibt es Finanzierungslücken, Kosten oder Nachteile?
                
                ---
                ## 📊 FAZIT-TABELLE
                Erstelle am Ende eine Tabelle: Partei | Hauptmaßnahme | Positiver Effekt | Hauptrisiko
                """

                # 3. Deine gewünschte Modell-Fallback-Liste
                preferred_models = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-1.5-flash"]
                
                response = None
                last_error = None

                # Schleife durch deine Modell-Prioritäten
                for model_name in preferred_models:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=[*[f[1] for f in gemini_files], prompt]
                        )
                        if response and response.text:
                            # Erfolgreicher Aufruf!
                            break
                    except Exception as e:
                        last_error = e
                        # Bei einem Fehler (z.B. 503 Überlastung) wird automatisch das nächste Modell probiert
                        continue

                # 4. Ergebnis ausgeben
                if response and response.text:
                    st.markdown("---")
                    st.markdown(response.text)
                else:
                    st.error(f"Alle gewählten Modelle waren überlastet oder nicht erreichbar. Letzter Fehler: {last_error}")

            except Exception as overall_e:
                st.error(f"Fehler während des Ablaufs: {overall_e}")

            finally:
                # 5. Hochgeladene Dateien immer bei Google löschen
                for _, g_file in gemini_files:
                    try:
                        client.files.delete(name=g_file.name)
                    except Exception:
                        pass
