import os
import glob
import streamlit as st
from google import genai
import pypdf

# Layout & Styling
st.set_page_config(page_title="PDV V1.1 (High Performance)", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !important; }
    .title-text { font-size: 2.2rem; font-weight: 700; color: #00FF66; margin-bottom: 0px; }
    .sub-text { color: #8B949E; font-size: 0.9rem; margin-bottom: 10px; }
    .pdf-info { color: #58A6FF; font-size: 0.85rem; margin-bottom: 15px; }
    .stButton>button { background-color: #238636 !important; color: #ffffff !important; border: 1px solid #2EA043 !important; width: 100%; }
</style>
""", unsafe_allow_html=True)

# API Key Check
api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("FEHLER: GEMINI_API_KEY fehlt!")
    st.stop()

client = genai.Client(api_key=api_key)
DATA_DIR = "data"

MODELS_TO_TRY = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite"
]

def get_pdf_page_count(filepath):
    try:
        reader = pypdf.PdfReader(filepath)
        return len(reader.pages)
    except Exception:
        return "?"

# --- UPLOAD & SESSION CACHING ---
if "uploaded_gemini_files" not in st.session_state:
    st.session_state.uploaded_gemini_files = {}

def get_cached_gemini_files(file_tuples):
    current_paths = {pdf_path for _, pdf_path, _ in file_tuples}
    
    # Alte nicht mehr benötigte Dateien bei Gemini löschen
    for cached_path in list(st.session_state.uploaded_gemini_files.keys()):
        if cached_path not in current_paths:
            try:
                client.files.delete(name=st.session_state.uploaded_gemini_files[cached_path].name)
            except Exception:
                pass
            del st.session_state.uploaded_gemini_files[cached_path]

    gemini_files = []
    for party_name, pdf_path, _ in file_tuples:
        if pdf_path not in st.session_state.uploaded_gemini_files:
            with st.spinner(f"Preloading PDF: {party_name}..."):
                g_file = client.files.upload(file=pdf_path)
                st.session_state.uploaded_gemini_files[pdf_path] = g_file
        gemini_files.append(st.session_state.uploaded_gemini_files[pdf_path])
        
    return gemini_files

# --- PRELOADED HOT TOPICS (STREAMLIT CACHED) ---
@st.cache_data(show_spinner="Analysiere Dokumente & generiere Hot Topics vor...")
def get_preloaded_hot_topics(file_tuples_keys, _api_key):
    """
    Berechnet die Hot Topics einmalig für das gesamte Set vor.
    Wird durch st.cache_data im RAM gehalten.
    """
    temp_client = genai.Client(api_key=_api_key)
    g_files = [st.session_state.uploaded_gemini_files[path] for _, path, _ in file_tuples_keys if path in st.session_state.uploaded_gemini_files]
    if not g_files:
        return ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]
    
    prompt = "Nenne 5-7 prägnante Hauptthemen/Schlagwörter dieser Parteiprogramme. Gib NUR eine kommagetrennte Liste zurück."
    
    for model_name in MODELS_TO_TRY:
        try:
            res = temp_client.models.generate_content(
                model=model_name,
                contents=[*g_files, prompt]
            )
            if res and res.text:
                return [t.strip() for t in res.text.split(",") if t.strip()]
        except Exception:
            continue

    return ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]

# --- SIDEBAR: KATEGORIE- AUSWAHL (FESTES SET AN STATT EINZELNER HÄKCHEN) ---
st.sidebar.markdown("### [1] Wahl / Kategorie")
categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))] if os.path.exists(DATA_DIR) else []

selected_files = []
if categories:
    category_map = {c.replace("_", " ").title(): c for c in categories}
    selected_label = st.sidebar.selectbox("Kategorie wählen:", list(category_map.keys()))
    selected_category = category_map[selected_label]
    
    # Automatisch ALLE PDFs dieser Kategorie als festes Set laden
    all_pdf_paths = glob.glob(os.path.join(DATA_DIR, selected_category, "*.pdf"))
    for pdf_path in sorted(all_pdf_paths):
        party_name = os.path.basename(pdf_path).replace(".pdf", "")
        pages = get_pdf_page_count(pdf_path)
        selected_files.append((party_name, pdf_path, pages))

# --- HEADER ---
st.markdown('<div class="title-text">> PDV V1.1 (High Performance)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Vorgeladene Deep-Analysis von Parteiprogrammen</div>', unsafe_allow_html=True)

if selected_files:
    info_str = " | ".join([f"<b>{name}</b> ({pg} S.)" for name, _, pg in selected_files])
    st.markdown(f'<div class="pdf-info">Geladenes Parteien-Set: {info_str}</div>', unsafe_allow_html=True)
    
    # PDFs einmalig hochladen/cachen
    active_g_files = get_cached_gemini_files(selected_files)
else:
    st.warning("Keine PDFs in dieser Kategorie gefunden.")

st.markdown("---")

if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = ""

# HOT TOPICS CHIPS (JETZT MIT PRELOADING)
if selected_files:
    st.markdown("### 🔥 Hot Topics (Vorgeladen)")
    # Übergabe als Hashable tuple für den Cache
    file_keys_tuple = tuple([(p[0], p[1], p[2]) for p in selected_files])
    auto_topics = get_preloaded_hot_topics(file_keys_tuple, api_key)
    
    cols = st.columns(min(len(auto_topics), 7))
    for idx, top_name in enumerate(auto_topics):
        if cols[idx % len(cols)].button(f"📌 {top_name}", key=f"ht_btn_{idx}"):
            st.session_state.selected_topic = top_name

st.markdown("---")

# THEMEN-EINGABE & ANALYSE
st.markdown("### [3] Thema analysieren")
topic = st.text_input("Thema eingeben oder oben ein Hot Topic anklicken:", value=st.session_state.selected_topic)

if st.button("ANALYSEN_STARTEN [ENTER]"):
    if not selected_files or not topic:
        st.warning("Bitte wähle ein Thema aus.")
    else:
        st.markdown("---")
        
        prompt = f"""
        Vergleiche ausführlich und neutral die Vorhaben der Parteien zum Thema: {topic}
        
        REGELN:
        1. Nutze AUSSCHLIESSLICH Informationen aus den hochgeladenen Parteiprogrammen.
        2. Gehe ins Detail und erläutere die jeweiligen Maßnahmen und Positionen umfassend.
        3. Führe Belege und Quellenangaben an, sofern im Text auffindbar [Quelle: Dateiname.pdf, S. X].
        4. Falls eine Partei zu dem Thema keine Aussagen trifft, gib dies explizit an.

        Antworte im Markdown-Format wie folgt:

        ## [PARTEI NAME]
        ### 1. GEPLANTE MASSNAHMEN & POSITIONEN
        - Ausführliche Beschreibung der konkreten Ziele, Forderungen und Vorhaben.

        ### 2. CHANCEN & POTENZIALE
        - Detaillierte Analyse der positiven Effekte und Chancen dieser Maßnahmen.

        ### 3. RISIKEN, LÜCKEN & KRITIKPUNKTE
        - Fundierte Analyse möglicher Risiken, unklarer Finanzierungen oder fehlender Aspekte.

        ---
        ## 📊 FAZIT & VERGLEICHSTABELLE
        Erstelle eine übersichtliche Zusammenfassungstabelle zum direkten Vergleich aller gewählten Parteien:
        Partei | Kernforderung / Hauptmaßnahme | Erwartete Wirkung | Haupthürde / Risiko
        """

        response_text = None
        last_error = None

        with st.spinner(f"Führe Echtzeit-Analyse für '{topic}' aus..."):
            for model_name in MODELS_TO_TRY:
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=[*active_g_files, prompt]
                    )
                    if res and res.text:
                        response_text = res.text
                        break
                except Exception as e:
                    last_error = e
                    continue

        if response_text:
            st.markdown(response_text)
        else:
            st.error(f"Fehler bei der Generierung der Analyse: {last_error}")
