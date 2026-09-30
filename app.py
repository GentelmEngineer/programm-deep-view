import os
import glob
import streamlit as st
from google import genai

# Design & Layout Setup
st.set_page_config(page_title="Programm Deep View", page_icon="⚡", layout="wide")

# CSS für den Hacker-/Terminal-Look (jetzt vollständig geschlossen)
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

                # Absicherung gegen Halluzinationen & externes Wissen
                prompt = f"""
                Du bist ein streng sachlicher und neutraler Analyst. 
                Vergleiche die Vorhaben der Parteien zum Thema: {topic}
                
                WICHTIGE REGELN:
                1. Nutze AUSSCHLIESSLICH Informationen aus den hochgeladenen Parteiprogrammen (PDF-Dateien).
                2. Erfinde KEINE Fakten, Spekulationen oder externe Informationen, die nicht im Text stehen.
                3. Falls eine Partei in ihrem Programm KEINE Aussagen zum Thema '{topic}' macht, schreibe explizit: "Keine spezifischen Angaben im Programm enthalten."
                
                Antworte extrem übersichtlich im Markdown-Format:
                ## [PARTEI NAME]
                ### 1. WAS GEPLANT IST
                - Zusammenfassung der im Text genannten Ziele.
                ### 2. POSITIVE KONSEQUENZEN (CHANCEN)
                - Vom Parteiprogramm genannte Erwartungen und Vorteile.
                ### 3. NEGATIVE KONSEQUENZEN (RISIKEN & LÜCKEN)
                - Im Text genannte Nachteile oder fehlende Details/Finanzierungsangaben.
                
                ---
                ## 📊 FAZIT-TABELLE
                Erstelle am Ende eine Tabelle: Partei | Hauptmaßnahme | Positiver Effekt | Hauptrisiko
                """

                # Liste robuster Modelle mit 2.5-flash-lite an erster Stelle
                models_to_try = [
                    "gemini-2.5-flash-lite",
                    "gemini-2.5-flash",
                    "gemini-2.0-flash-lite"
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
                            break  # Analyse erfolgreich
                    except Exception as err:
                        last_error = err
                        continue

                if response and response.text:
                    st.markdown("---")
                    st.markdown(response.text)
                else:
                    st.error(f"Fehler bei allen Modellen: {last_error}")

            except Exception as e:
                st.error(f"Allgemeiner Fehler: {eThe error happens because a triple-quoted string starting on line 10 was opened using `"""` but never properly closed before line 39 (or the end of the file).

### Common Causes & Fixes

**1. Missing Closing Quotes**
You opened the string with `"""` on line 10, but forgot to add the closing `"""` at the end of your Markdown text.

```python
# INCORRECT
st.markdown("""
# Welcome to Deep View
This is a multi-line string.

# CORRECT
st.markdown("""
# Welcome to Deep View
This is a multi-line string.
""")  # <--- Ensure this closing triple-quote is present
