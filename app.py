import os
import glob
import streamlit as st
from google import genai

# Design & Layout Setup
st.set_page_config(page_title="PDV V1.1", page_icon="⚡", layout="wide")

# CSS für den Hacker-/Terminal-Look
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !important; }
    .title-text { font-size: 2.2rem; font-weight: 700; color: #00FF66; margin-bottom: 0px; }
    .sub-text { color: #8B949E; font-size: 0.9rem; margin-bottom: 10px; }
    .pdf-list { color: #58A6FF; font-size: 0.9rem; font-weight: bold; margin-bottom: 20px; }
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

# Ordner scannen (Vorab laden, um die PDFs unter dem Titel anzeigen zu können)
DATA_DIR = "data"
categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))] if os.path.exists(DATA_DIR) else []

pdf_files = []
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

# Main Header
st.markdown('<div class="title-text">> PDV V1.1</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Deep-Analysis von Parteiprogrammen & Konsequenzen-Check</div>', unsafe_allow_html=True)

# Geladene PDFs direkt unter dem Titel anzeigen
if pdf_files:
    pdf_names = [os.path.basename(p) for p in pdf_files]
    st.markdown(f'<div class="pdf-list">Aktive Dokumente: {", ".join(pdf_names)}</div>', unsafe_allow_html=True)

st.markdown("---")

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

                # Absicherung gegen Halluzinationen & Quellenangabe-Pflicht
                prompt = f"""
                Du bist ein streng sachlicher und neutraler Analyst. 
                Vergleiche die Vorhaben der Parteien zum Thema: {topic}
                
                WICHTIGE REGELN:
                1. Nutze AUSSCHLIESSLICH Informationen aus den hochgeladenen Parteiprogrammen (PDF-Dateien).
                2. Erfinde KEINE Fakten, Spekulationen oder externe Informationen.
                3. Falls eine Partei in ihrem Programm KEINE Aussagen zum Thema '{topic}' macht, schreibe explizit: "Wird im Parteiprogramm nicht erwähnt." Das ist eine völlig legitime Antwort!
                
                Antworte extrem übersichtlich im Markdown-Format:
                ## [PARTEI NAME]
                ### 1. WAS GEPLANT IST
                - Zusammenfassung der im Text genannten Ziele.
                - WICHTIG: Gib hier bei jeder einzelnen Aussage zwingend die genaue Quelle an (Name der PDF-Datei und die Seitenzahl, z.B. [Quelle: Dateiname.pdf, S. 12]).
                ### 2. POSITIVE KONSEQUENZEN (CHANCEN)
                - Vom Parteiprogramm genannte Erwartungen und Vorteile. (Hier ist keine Seitenangabe nötig).
                ### 3. NEGATIVE KONSEQUENZEN (RISIKEN & LÜCKEN)
                - Im Text genannte Nachteile oder fehlende Details/Finanzierungsangaben. (Hier ist keine Seitenangabe nötig).
                
                ---
                ## 📊 FAZIT-TABELLE
                Erstelle am Ende eine Tabelle: Partei | Hauptmaßnahme | Positiver Effekt | Hauptrisiko
                """

                # Gewünschte Modelle in Prioritätsreihenfolge
                models_to_try = [
                    "gemini-3.8-flash",
                    "gemini-3.7-flash",
                    "gemini-3.5-flash-lite"
                ]
                
                response = None
                last_error = None

                # Automatische Ausweich-Schleife
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
                st.error(f"Allgemeiner Fehler: {e}")

            finally:
                # Aufräumen der temporären Dateien bei Google
                for _, g_file in gemini_files:
                    try:
                        client.files.delete(name=g_file.name)
                    except Exception:
                        pass
