import os
import glob
import streamlit as st
from google import genai
import pypdf

# Design & Layout Setup
st.set_page_config(page_title="PDV V1.1", page_icon="⚡", layout="wide")

# CSS für den Hacker-/Terminal-Look
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !important; }
    .title-text { font-size: 2.2rem; font-weight: 700; color: #00FF66; margin-bottom: 0px; }
    .sub-text { color: #8B949E; font-size: 0.9rem; margin-bottom: 10px; }
    .pdf-info { color: #58A6FF; font-size: 0.85rem; margin-bottom: 15px; }
    .hot-topic-badge { display: inline-block; background-color: #1F6FEB; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; margin-right: 5px; margin-bottom: 5px; }
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

# Ordner scannen
DATA_DIR = "data"
categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))] if os.path.exists(DATA_DIR) else []

# Hilfsfunktion: Seitenzahl auslesen
def get_pdf_page_count(filepath):
    try:
        reader = pypdf.PdfReader(filepath)
        return len(reader.pages)
    except Exception:
        return "?"

st.sidebar.markdown("### [1] Wahl auswählen")
selected_files = []

if categories:
    category_map = {c.replace("_", " ").title(): c for c in categories}
    selected_label = st.sidebar.selectbox("Kategorie:", list(category_map.keys()))
    selected_category = category_map[selected_label]
    
    all_pdf_paths = glob.glob(os.path.join(DATA_DIR, selected_category, "*.pdf"))
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### [2] Parteien auswählen")
    
    # Checkbox-Auswahl für jede Partei inkl. Seitenzahl
    for pdf_path in sorted(all_pdf_paths):
        party_name = os.path.basename(pdf_path).replace(".pdf", "")
        pages = get_pdf_page_count(pdf_path)
        
        # Standardmäßig sind alle Parteien angekreuzt
        is_selected = st.sidebar.checkbox(
            f"{party_name} ({pages} S.)", 
            value=True, 
            key=pdf_path
        )
        if is_selected:
            selected_files.append((party_name, pdf_path, pages))

else:
    st.sidebar.error("Keine Ordner in 'data/' gefunden.")

# Main Header
st.markdown('<div class="title-text">> PDV V1.1</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Deep-Analysis von Parteiprogrammen & Konsequenzen-Check</div>', unsafe_allow_html=True)

# Vorschau der ausgewählten PDFs & Seitenzahlen unter dem Titel
if selected_files:
    info_str = " | ".join([f"<b>{name}</b> ({pg} Seiten)" for name, _, pg in selected_files])
    st.markdown(f'<div class="pdf-info">Ausgewählte Programme: {info_str}</div>', unsafe_allow_html=True)
else:
    st.warning("Bitte wähle in der Seitenleiste mindestens eine Partei aus.")

st.markdown("---")

# Hot Topics ermitteln (mittels Button oder automatischer Generierung)
st.markdown("### 🔥 Hot Topics (Gemeinsame Themen)")
if st.button("HOT TOPICS ERMITTELN"):
    if not selected_files:
        st.error("Keine Parteien ausgewählt!")
    else:
        with st.spinner("Scanne Parteiprogramme nach gemeinsamen Hauptthemen..."):
            gemini_files = []
            try:
                for party_name, pdf_path, _ in selected_files:
                    g_file = client.files.upload(file=pdf_path)
                    gemini_files.append((party_name, g_file))

                hot_topic_prompt = """
                Analysiere die hochgeladenen Parteiprogramme.
                Nenne genau 5 bis 8 prägnante Themen/Schlagwörter (z. B. Mieten, Digitalisierung, Rentenreform, Klimaschutz), die in ALLEN diesen Programmen behandelt werden.
                Gib NUR eine kommagetrennte Liste der Themen zurück, sonst nichts.
                """

                models_to_try = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]
                ht_response = None

                for m in models_to_try:
                    try:
                        ht_response = client.models.generate_content(
                            model=m,
                            contents=[*[f[1] for f in gemini_files], hot_topic_prompt]
                        )
                        if ht_response and ht_response.text:
                            break
                    except Exception:
                        continue

                if ht_response and ht_response.text:
                    topics_list = [t.strip() for t in ht_response.text.split(",")]
                    badges_html = "".join([f'<span class="hot-topic-badge">{t}</span>' for t in topics_list])
                    st.markdown(f"<div>{badges_html}</div>", unsafe_allow_html=True)
                else:
                    st.error("Fehler beim Abrufen der Hot Topics.")

            except Exception as e:
                st.error(f"Fehler: {e}")

            finally:
                for _, g_file in gemini_files:
                    try:
                        client.files.delete(name=g_file.name)
                    except Exception:
                        pass

st.markdown("---")

# Thema-Eingabe
st.markdown("### [3] Thema analysieren")
topic = st.text_input("Gib ein Thema ein (oder wähle eines aus den Hot Topics):")

if st.button("ANALYSEN_STARTEN [ENTER]"):
    if not selected_files:
        st.error("Keine Parteien ausgewählt!")
    elif not topic:
        st.warning("Bitte gib zuerst ein Thema ein.")
    else:
        with st.spinner("Lese Parteiprogramme und analysiere Konsequenzen..."):
            gemini_files = []
            try:
                # Nur die ausgewählten PDFs hochladen
                for party_name, pdf_path, _ in selected_files:
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
                            break
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
