import os
import glob
import streamlit as st
from google import genai
import pypdf

# Layout & Styling
st.set_page_config(page_title="PDV V1.1 (Fast Stream)", page_icon="⚡", layout="wide")

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

def get_pdf_page_count(filepath):
    try:
        reader = pypdf.PdfReader(filepath)
        return len(reader.pages)
    except Exception:
        return "?"

# --- CACHING DER UPLOADS IM SESSION STATE ---
if "uploaded_gemini_files" not in st.session_state:
    st.session_state.uploaded_gemini_files = {}

def get_cached_gemini_files(file_tuples):
    """
    Lädt PDFs nur hoch, wenn sie nicht bereits in st.session_state gelagert sind.
    Gibt die Liste der Gemini-File-Objekte zurück.
    """
    current_paths = {pdf_path for _, pdf_path, _ in file_tuples}
    
    # Alte Uploads löschen, die nicht mehr ausgewählt sind
    for cached_path in list(st.session_state.uploaded_gemini_files.keys()):
        if cached_path not in current_paths:
            try:
                client.files.delete(name=st.session_state.uploaded_gemini_files[cached_path].name)
            except Exception:
                pass
            del st.session_state.uploaded_gemini_files[cached_path]

    # Neue PDFs hochladen, falls noch nicht gecached
    gemini_files = []
    for party_name, pdf_path, _ in file_tuples:
        if pdf_path not in st.session_state.uploaded_gemini_files:
            with st.spinner(f"Lade PDF hoch: {party_name}..."):
                g_file = client.files.upload(file=pdf_path)
                st.session_state.uploaded_gemini_files[pdf_path] = g_file
        gemini_files.append(st.session_state.uploaded_gemini_files[pdf_path])
        
    return gemini_files

# --- HOT TOPICS GENERIERUNG ---
@st.cache_data(show_spinner="Ermittle Hot Topics...")
def get_hot_topics(file_tuples, _api_key):
    temp_client = genai.Client(api_key=_api_key)
    # Nutzen vorgehaltene Uploads
    g_files = [st.session_state.uploaded_gemini_files[path] for _, path, _ in file_tuples if path in st.session_state.uploaded_gemini_files]
    if not g_files:
        return ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]
    
    prompt = "Nenne 5-7 prägnante Hauptthemen/Schlagwörter dieser Parteiprogramme. Gib NUR eine kommagetrennte Liste zurück."
    try:
        res = temp_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[*g_files, prompt]
        )
        if res and res.text:
            return [t.strip() for t in res.text.split(",") if t.strip()]
    except Exception:
        pass
    return ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]

# --- SIDEBAR & PARTEIAUSWAHL ---
st.sidebar.markdown("### [1] Wahl auswählen")
categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))] if os.path.exists(DATA_DIR) else []

selected_files = []
if categories:
    category_map = {c.replace("_", " ").title(): c for c in categories}
    selected_label = st.sidebar.selectbox("Kategorie:", list(category_map.keys()))
    selected_category = category_map[selected_label]
    
    all_pdf_paths = glob.glob(os.path.join(DATA_DIR, selected_category, "*.pdf"))
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### [2] Parteien auswählen")
    for pdf_path in sorted(all_pdf_paths):
        party_name = os.path.basename(pdf_path).replace(".pdf", "")
        pages = get_pdf_page_count(pdf_path)
        if st.sidebar.checkbox(f"{party_name} ({pages} S.)", value=True, key=pdf_path):
            selected_files.append((party_name, pdf_path, pages))

# --- HEADER ---
st.markdown('<div class="title-text">> PDV V1.1 (Ultra-Fast Stream)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Deep-Analysis von Parteiprogrammen in Echtzeit</div>', unsafe_allow_html=True)

if selected_files:
    info_str = " | ".join([f"<b>{name}</b> ({pg} S.)" for name, _, pg in selected_files])
    st.markdown(f'<div class="pdf-info">Ausgewählte Programme: {info_str}</div>', unsafe_allow_html=True)
    # Uploads einmalig/gecached durchführen
    active_g_files = get_cached_gemini_files(selected_files)
else:
    st.warning("Bitte wähle mindestens eine Partei aus.")

st.markdown("---")

if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = ""

# HOT TOPICS CHIPS
if selected_files:
    st.markdown("### 🔥 Hot Topics")
    files_tuple = tuple(selected_files)
    auto_topics = get_hot_topics(files_tuple, api_key)
    
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
        st.warning("Bitte wähle Parteien und ein Thema aus.")
    else:
        st.markdown("---")
        
        prompt = f"""
        Vergleiche neutral die Vorhaben der Parteien zum Thema: {topic}
        REGELN:
        1. Nutze AUSSCHLIESSLICH Informationen aus den hochgeladenen Parteiprogrammen.
        2. Halte dich EXTREM kurz und präzise (maximal 3 Stichpunkte pro Kategorie).
        3. Falls eine Partei dazu nichts sagt, schreibe: "Wird im Parteiprogramm nicht erwähnt."
        
        Antworte im Markdown-Format:
        ## [PARTEI NAME]
        ### 1. WAS GEPLANT IST
        - Ziel [Quelle: Dateiname.pdf, S. X]
        ### 2. CHANCEN
        - Positiver Effekt
        ### 3. RISIKEN & LÜCKEN
        - Risiko / Lücke
        
        ---
        ## 📊 FAZIT-TABELLE
        Partei | Hauptmaßnahme | Positiver Effekt | Hauptrisiko
        """

        # STREAMING EXECUTION
        def stream_generator():
            try:
                response = client.models.generate_content_stream(
                    model="gemini-2.5-flash",
                    contents=[*active_g_files, prompt]
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
            except Exception as e:
                yield f"\n\n**Fehler bei der Analyse:** {e}"

        # Live-Anzeige per Stream
        st.write_stream(stream_generator())
