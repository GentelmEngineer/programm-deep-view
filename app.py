import os
import json
import glob
import streamlit as st
from google import genai
import pypdf

# Layout & Styling
st.set_page_config(page_title="PDV V1.1 (Smart Cache)", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !important; }
    .title-text { font-size: 2.2rem; font-weight: 700; color: #00FF66; margin-bottom: 0px; }
    .sub-text { color: #8B949E; font-size: 0.9rem; margin-bottom: 10px; }
    .pdf-info { color: #58A6FF; font-size: 0.85rem; margin-bottom: 15px; }
    .stButton>button { background-color: #238636 !important; color: #ffffff !important; border: 1px solid #2EA043 !important; width: 100%; }
</style>
""", unsafe_allow_html=True)

api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("FEHLER: GEMINI_API_KEY fehlt!")
    st.stop()

client = genai.Client(api_key=api_key)
DATA_DIR = "data"

MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite"
]

def get_pdf_page_count(filepath):
    try:
        reader = pypdf.PdfReader(filepath)
        return len(reader.pages)
    except Exception:
        return "?"

if "uploaded_gemini_files" not in st.session_state:
    st.session_state.uploaded_gemini_files = {}

def get_cached_gemini_files(file_tuples):
    current_paths = {pdf_path for _, pdf_path, _ in file_tuples}
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
            g_file = client.files.upload(file=pdf_path)
            st.session_state.uploaded_gemini_files[pdf_path] = g_file
        gemini_files.append(st.session_state.uploaded_gemini_files[pdf_path])
    return gemini_files

# --- LÄDT HOT TOPICS & FERTIGE ANALYSEN ---
def load_precomputed_data(category_path):
    topics = ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]
    analyses = {}
    
    ht_path = os.path.join(category_path, "hot_topics.json")
    if os.path.exists(ht_path):
        try:
            with open(ht_path, "r", encoding="utf-8") as f:
                topics = json.load(f)
        except Exception:
            pass
            
    an_path = os.path.join(category_path, "hot_topic_analyses.json")
    if os.path.exists(an_path):
        try:
            with open(an_path, "r", encoding="utf-8") as f:
                analyses = json.load(f)
        except Exception:
            pass
            
    return topics, analyses

# Speichert neue Analysen direkt in die JSON-Datei im Ordner
def save_analysis_to_json(category_path, topic, analysis_text):
    an_path = os.path.join(category_path, "hot_topic_analyses.json")
    analyses = {}
    if os.path.exists(an_path):
        try:
            with open(an_path, "r", encoding="utf-8") as f:
                analyses = json.load(f)
        except Exception:
            pass
    
    analyses[topic] = analysis_text
    try:
        with open(an_path, "w", encoding="utf-8") as f:
            json.dump(analyses, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Konnte Analyse nicht lokal cachen: {e}")

# --- SIDEBAR: KATEGORIE- AUSWAHL ---
st.sidebar.markdown("### [1] Wahl / Kategorie")
categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))] if os.path.exists(DATA_DIR) else []

selected_files = []
auto_topics = []
precomputed_analyses = {}
selected_category_path = ""

if categories:
    category_map = {c.replace("_", " ").title(): c for c in categories}
    selected_label = st.sidebar.selectbox("Kategorie wählen:", list(category_map.keys()))
    selected_category = category_map[selected_label]
    selected_category_path = os.path.join(DATA_DIR, selected_category)
    
    auto_topics, precomputed_analyses = load_precomputed_data(selected_category_path)
    
    all_pdf_paths = glob.glob(os.path.join(selected_category_path, "*.pdf"))
    for pdf_path in sorted(all_pdf_paths):
        party_name = os.path.basename(pdf_path).replace(".pdf", "")
        pages = get_pdf_page_count(pdf_path)
        selected_files.append((party_name, pdf_path, pages))

# --- HEADER ---
st.markdown('<div class="title-text">> PDV V1.1 (Smart Cache)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Intelligente Parteiprogramm-Analyse mit Selbst-Caching</div>', unsafe_allow_html=True)

if selected_files:
    info_str = " | ".join([f"<b>{name}</b> ({pg} S.)" for name, _, pg in selected_files])
    st.markdown(f'<div class="pdf-info">Geladenes Parteien-Set: {info_str}</div>', unsafe_allow_html=True)
    active_g_files = get_cached_gemini_files(selected_files)
else:
    st.warning("Keine PDFs in dieser Kategorie gefunden.")

st.markdown("---")

if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = ""

# HOT TOPICS CHIPS
if selected_files and auto_topics:
    st.markdown("### 🔥 Hot Topics (Instant wenn gecached)")
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
        
        # 1. PRÜFEN OB BEREITS GESPEICHERT (CACHE)
        if topic in precomputed_analyses:
            st.info(⚡ Lade fertige Analyse aus dem System-Cache...")
            st.markdown(precomputed_analyses[topic])
        else:
            # 2. LIVE-API CALL (BEim ersten Mal)
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

            with st.spinner(f"Führe Erstanalyse für '{topic}' aus und speichere ab..."):
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
                # Direkt in die JSON-Datei schreiben, damit es ab sofort fix da ist!
                save_analysis_to_json(selected_category_path, topic, response_text)
            else:
                st.error(f"Fehler bei der Generierung der Analyse: {last_error}")
