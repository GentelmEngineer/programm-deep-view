import os
import json
import glob
import re
import streamlit as st
from google import genai
from google.genai.types import HttpOptions
import pypdf

# Layout & Styling
st.set_page_config(page_title="VoteCore", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !important; }
    
    .title-box {
        position: relative;
        padding: 20px 25px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        background-color: #161b22;
        margin-bottom: 20px;
        border-radius: 6px;
    }
    .title-box::before, .title-box::after {
        content: '';
        position: absolute;
        width: 10px;
        height: 10px;
        border-color: #ffffff;
        border-style: solid;
    }
    .title-box::before {
        top: -1px;
        left: -1px;
        border-width: 2px 0 0 2px;
    }
    .title-box::after {
        bottom: -1px;
        right: -1px;
        border-width: 0 2px 2px 0;
    }
    
    .title-text { font-size: 2.5rem; font-weight: 700; color: #ffffff; margin-bottom: 0px; letter-spacing: 1px; }
    .sub-text { color: #8B949E; font-size: 0.9rem; margin-top: 5px; margin-bottom: 0px; }
    
    .pdf-info { 
        background-color: #161b22; 
        border: 1px solid rgba(255, 255, 255, 0.15); 
        padding: 10px 15px; 
        border-radius: 6px; 
        color: #C9D1D9; 
        font-size: 0.85rem; 
        margin-bottom: 15px; 
    }
    
    .agent-status {
        background-color: #21262d;
        border-left: 3px solid #58a6ff;
        padding: 8px 12px;
        margin-bottom: 10px;
        font-size: 0.8rem;
        color: #8b949e;
        border-radius: 0 6px 6px 0;
    }
    
    .stButton>button { 
        background-color: #161b22 !important; 
        color: #ffffff !important; 
        border: 1px solid #30363d !important; 
        width: 100%; 
        border-radius: 6px; 
        font-weight: bold; 
    }
    .stButton>button:hover {
        background-color: #21262d !important;
        border-color: #8b949e !important;
    }
    
    .source-citation {
        color: #8B949E !important;
        font-size: 0.8rem !important;
        font-style: italic;
    }
    
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: transparent; color: #8B949E; text-align: right; padding-right: 20px; font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("FEHLER: GEMINI_API_KEY fehlt!")
    st.stop()

# Client mit 90 Sekunden Timeout für Sicherheit
client = genai.Client(
    api_key=api_key, 
    http_options=HttpOptions(timeout=90 * 1000)
)
DATA_DIR = "data"

MODEL_NAME = "gemini-3.5-flash-lite"

def get_pdf_page_count(filepath):
    try:
        reader = pypdf.PdfReader(filepath)
        return len(reader.pages)
    except Exception:
        return "?"

def get_cached_gemini_files(file_tuples, category_path):
    cache_path = os.path.join(category_path, "gemini_files_cache.json")
    cloud_file_map = {}
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cloud_file_map = json.load(f)
        except Exception:
            pass

    gemini_files = []
    updated = False

    for party_name, pdf_path, _ in file_tuples:
        file_basename = os.path.basename(pdf_path)
        g_file = None
        
        if file_basename in cloud_file_map:
            remote_name = cloud_file_map[file_basename]
            try:
                g_file = client.files.get(name=remote_name)
            except Exception:
                g_file = None

        if not g_file:
            with st.spinner(f"Lade '{party_name}' einmalig in die Gemini-Cloud hoch..."):
                g_file = client.files.upload(file=pdf_path)
                cloud_file_map[file_basename] = g_file.name
                updated = True

        gemini_files.append(g_file)

    if updated:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cloud_file_map, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return gemini_files

def load_cached_hot_topics(category_path):
    ht_path = os.path.join(category_path, "hot_topics.json")
    if os.path.exists(ht_path):
        try:
            with open(ht_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    return None

def save_hot_topics_to_json(category_path, topics):
    ht_path = os.path.join(category_path, "hot_topics.json")
    try:
        with open(ht_path, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Konnte Hot Topics nicht cachen: {e}")

def get_hot_topics(file_tuples, category_path, active_g_files, _api_key):
    cached_topics = load_cached_hot_topics(category_path)
    if cached_topics:
        return cached_topics

    fallback_topics = ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]
    if not active_g_files:
        return fallback_topics
    
    prompt = "Nenne exakt 5 prägnante Hauptthemen/Schlagwörter dieser Parteiprogramme. Gib NUR eine kommaseparierte Liste zurück."
    
    try:
        res = client.models.generate_content(
            model=MODEL_NAME,
            contents=[*active_g_files, prompt]
        )
        if res and res.text:
            parsed = [t.strip() for t in res.text.split(",") if t.strip()][:5]
            if len(parsed) >= 3:
                save_hot_topics_to_json(category_path, parsed)
                return parsed
    except Exception:
        pass

    return fallback_topics

def load_precomputed_analyses(category_path):
    analyses = {}
    an_path = os.path.join(category_path, "hot_topic_analyses.json")
    if os.path.exists(an_path):
        try:
            with open(an_path, "r", encoding="utf-8") as f:
                analyses = json.load(f)
        except Exception:
            pass
    return analyses

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

def format_sources_in_text(text):
    pattern = r'(\[.*?S\.\s*\d+.*?\]|\[Quelle:.*?\])'
    return re.sub(pattern, r'<span class="source-citation">\1</span>', text)

# --- HEADER & TITEL ---
st.markdown("""
<div class="title-box">
    <div class="title-text">VoteCore</div>
    <div class="sub-text">Deep-Analysis von Parteiprogrammen (Multi-Agent Pipeline)</div>
</div>
""", unsafe_allow_html=True)

# --- WAHLORDNER / KATEGORIE AUSWAHL ---
DATA_DIR = "data"
categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))] if os.path.exists(DATA_DIR) else []

selected_files = []
selected_category_path = ""
precomputed_analyses = {}

if categories:
    category_map = {c.replace("_", " ").title(): c for c in categories}
    selected_label = st.selectbox("Wahl / Kategorie auswählen:", list(category_map.keys()))
    selected_category = category_map[selected_label]
    selected_category_path = os.path.join(DATA_DIR, selected_category)
    
    all_pdf_paths = glob.glob(os.path.join(selected_category_path, "*.pdf"))
    for pdf_path in sorted(all_pdf_paths):
        party_name = os.path.basename(pdf_path).replace(".pdf", "")
        pages = get_pdf_page_count(pdf_path)
        selected_files.append((party_name, pdf_path, pages))
    
    precomputed_analyses = load_precomputed_analyses(selected_category_path)

if selected_files:
    info_str = " | ".join([f"<b>{name}</b> ({pg} S.)" for name, _, pg in selected_files])
    st.markdown(f'<div class="pdf-info">Aktives Parteien-Set: {info_str}</div>', unsafe_allow_html=True)
    active_g_files = get_cached_gemini_files(selected_files, selected_category_path)
else:
    st.warning("Keine PDFs in dieser Kategorie gefunden.")

st.markdown("---")

if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = ""

# HOT TOPICS
if selected_files:
    st.markdown("### 🔥 Hot Topics")
    file_keys_tuple = tuple([(p[0], p[1], p[2]) for p in selected_files])
    auto_topics = get_hot_topics(file_keys_tuple, selected_category_path, active_g_files, api_key)
    
    num_topics = len(auto_topics) if len(auto_topics) > 0 else 5
    cols = st.columns(num_topics)
    for idx, top_name in enumerate(auto_topics):
        with cols[idx]:
            if st.button(f"📌 {top_name}", key=f"ht_btn_{idx}DATA"):
                st.session_state.selected_topic = top_name

st.markdown("---")

# THEMEN-EINGABE & ANALYSE
st.markdown("### 📖 Thema analysieren")
topic = st.text_input("Thema eingeben oder oben ein Hot Topic anklicken:", value=st.session_state.selected_topic)

if st.button("Starte Multi-Agenten-Analyse"):
    if not selected_files or not topic:
        st.warning("Bitte wähle ein Thema aus.")
    else:
        st.markdown("---")
        is_hot_topic = (topic in auto_topics)
        
        def render_analysis_text(full_text):
            parts = full_text.split("## ")
            for part in parts:
                if not part.strip():
                    continue
                    
                lines = part.split("\n")
                party_title = lines[0].strip()
                
                massnahme_summary = "Keine Kurzzusammenfassung verfügbar."
                massnahme_details = []
                chance_summary = "Keine Kurzzusammenfassung verfügbar."
                chance_details = []
                risiko_summary = "Keine Kurzzusammenfassung verfügbar."
                risiko_details = []
                
                current_section = ""
                for line in lines[1:]:
                    if "MASSNAHMEN_SUMMARY:" in line:
                        massnahme_summary = line.replace("**MASSNAHMEN_SUMMARY:**", "").strip()
                        current_section = "massnahmen"
                        continue
                    elif "CHANCEN_SUMMARY:" in line:
                        chance_summary = line.replace("**CHANCEN_SUMMARY:**", "").strip()
                        current_section = "chancen"
                        continue
                    elif "RISIKEN_SUMMARY:" in line:
                        risiko_summary = line.replace("**RISIKEN_SUMMARY:**", "").strip()
                        current_section = "risiken"
                        continue
                    
                    if current_section == "massnahmen" and line.strip():
                        massnahme_details.append(line)
                    elif current_section == "chancen" and line.strip():
                        chance_details.append(line)
                    elif current_section == "risiken" and line.strip():
                        risiko_details.append(line)
                
                st.markdown(f"### {party_title}")
                
                st.markdown(f"- **Detaillierte Maßnahmen:** {format_sources_in_text(massnahme_summary)}", unsafe_allow_html=True)
                with st.expander("➕ Mehr Details & Quellen zu Maßnahmen"):
                    st.markdown("\n".join([format_sources_in_text(d) for d in massnahme_details]), unsafe_allow_html=True)
                
                st.markdown(f"- **Chancen:** {format_sources_in_text(chance_summary)}", unsafe_allow_html=True)
                with st.expander("➕ Mehr Details & Quellen zu Chancen"):
                    st.markdown("\n".join([format_sources_in_text(d) for d in chance_details]), unsafe_allow_html=True)
                
                st.markdown(f"- **Risiken & Lücken:** {format_sources_in_text(risiko_summary)}", unsafe_allow_html=True)
                with st.expander("➕ Mehr Details & Quellen zu Risiken & Lücken"):
                    st.markdown("\n".join([format_sources_in_text(d) for d in risiko_details]), unsafe_allow_html=True)
                
                st.markdown("---")

        if is_hot_topic and topic in precomputed_analyses:
            render_analysis_text(precomputed_analyses[topic])
        else:
            status_box = st.empty()
            
            try:
                # --- AGENT 1: Der Analyst (Extrahiert harte Maßnahmen aus PDFs) ---
                status_box.markdown('<div class="agent-status">🤖 Agent 1 (Analyst) extrahiert die konkreten Maßnahmen aus den Programmen...</div>', unsafe_allow_html=True)
                
                prompt_agent1 = f"""
                Analysiere neutral die konkreten Vorhaben und Maßnahmen der Parteien zum Thema: {topic}
                Nutze ausschliesslich die hochgeladenen Parteiprogramme.
                Extrahiere pro Partei exakt die 3 wesentlichen Maßnahmen inkl. Quellenangabe [Quelle: Dateiname.pdf, S. X].

                Antworte strikt im Format:
                ## [PARTEI NAME]
                **MASSNAHMEN_SUMMARY:** [Kurzer Satz zur Hauptmaßnahme]
                - **Detaillierte Vorhaben & Belege:**
                  - 1. ... [Quelle: ...]
                  - 2. ... [Quelle: ...]
                  - 3. ... [Quelle: ...]
                """
                
                res1 = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[*active_g_files, prompt_agent1]
                )
                agent1_output = res1.text if res1 and res1.text else ""

                # --- AGENT 2: Der Chancen-Ableiter (Nimmt Agent 1 Text, liest keine PDFs neu!) ---
                status_box.markdown('<div class="agent-status">🤖 Agent 2 (Chancen-Analyst) leitet Potenziale aus den Maßnahmen ab...</div>', unsafe_allow_html=True)
                
                prompt_agent2 = f"""
                Hier sind die extrahierten Maßnahmen der Parteien zum Thema '{topic}':
                {agent1_output}

                Deine Aufgabe als Chancen-Analyst: Leite basierend NUR auf diesen Maßnahmen für jede Partei exakt die 3 wesentlichen Chancen/Potenziale ab.
                Behalte die exakte Parteistruktur bei und füge folgendes Format hinzu:
                **CHANCEN_SUMMARY:** [Kurzer Satz zur Hauptchance]
                - **Detaillierte Potenziale & Belege:**
                  - 1. ...
                  - 2. ...
                  - 3. ...
                """
                
                res2 = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[prompt_agent2]
                )
                agent2_output = res2.text if res2 and res2.text else ""

                # --- AGENT 3: Der Kritiker & Risiko-Prüfer (Kombiniert & prüft kritisch) ---
                status_box.markdown('<div class="agent-status">🤖 Agent 3 (Kritiker & Risiko-Prüfer) hinterfragt die Umsetzbarkeit und deckt Lücken auf...</div>', unsafe_allow_html=True)
                
                prompt_agent3 = f"""
                Hier ist die bisherige Analyse zum Thema '{topic}':
                {agent2_output}

                Deine Aufgabe als kritischer Prüfer: Hinterfrage die Vorhaben und Maßnahmen kritisch. Beleuchte Umsetzungsrisiken, Finanzierungshürden oder logische Lücken. 
                Füge für jede Partei im gleichen Format die Risiken hinzu:
                **RISIKEN_SUMMARY:** [Kurzer Satz zum Hauptrisiko]
                - **Detaillierte Risiken & Lücken:**
                  - 1. ...
                  - 2. ...
                  - 3. ...

                Gib den finalen, vollständigen Text für alle Parteien in exakt diesem Schema aus (ohne zusätzlichen Einleitungstext):
                ## [PARTEI NAME]
                **MASSNAHMEN_SUMMARY:** ...
                - **Detaillierte Vorhaben & Belege:** ...
                **CHANCEN_SUMMARY:** ...
                - **Detaillierte Potenziale & Belege:** ...
                **RISIKEN_SUMMARY:** ...
                - **Detaillierte Risiken & Lücken:** ...
                """
                
                res3 = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[prompt_agent3]
                )
                final_response = res3.text if res3 and res3.text else ""
                
                status_box.empty()

                if final_response:
                    render_analysis_text(final_response)
                    if is_hot_topic:
                        save_analysis_to_json(selected_category_path, topic, final_response)
                else:
                    st.error("Fehler: Die Agenten-Pipeline lieferte keinen Text.")

            except Exception as e:
                status_box.empty()
                st.error(f"Fehler bei der Multi-Agenten-Analyse: {e}")

# --- FUßNOTE MIT VERSION ---
st.markdown('<div class="footer">VoteCore V1.4 (Multi-Agent)</div>', unsafe_allow_html=True)
