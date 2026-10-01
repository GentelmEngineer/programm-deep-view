import os
import json
import glob
import streamlit as st
from google import genai
import pypdf

# Layout & Styling
st.set_page_config(page_title="PDV V1.1", page_icon="⚡", layout="wide")

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

# Modell-Reihenfolge
MODELS_TO_TRY = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash"
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

# --- HOT TOPICS MIT LOKALEM CACHE (JSON) ---
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

def get_hot_topics(file_tuples, category_path, _api_key):
    cached_topics = load_cached_hot_topics(category_path)
    if cached_topics:
        return cached_topics

    temp_client = genai.Client(api_key=_api_key)
    g_files = [st.session_state.uploaded_gemini_files[path] for _, path, _ in file_tuples if path in st.session_state.uploaded_gemini_files]
    
    fallback_topics = ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]
    if not g_files:
        return fallback_topics
    
    prompt = "Nenne exakt 5 prägnante Hauptthemen/Schlagwörter dieser Parteiprogramme. Gib NUR eine kommaseparierte Liste zurück."
    
    generated_topics = None
    for model_name in MODELS_TO_TRY:
        try:
            res = temp_client.models.generate_content(
                model=model_name,
                contents=[*g_files, prompt]
            )
            if res and res.text:
                parsed = [t.strip() for t in res.text.split(",") if t.strip()][:5]
                if len(parsed) >= 3:
                    generated_topics = parsed
                    break
        except Exception:
            continue

    if not generated_topics:
        generated_topics = fallback_topics

    save_hot_topics_to_json(category_path, generated_topics)
    return generated_topics

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

# --- SIDEBAR: KATEGORIE- AUSWAHL ---
st.sidebar.markdown("### [1] Wahl / Kategorie")
categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))] if os.path.exists(DATA_DIR) else []

selected_files = []
selected_category_path = ""
precomputed_analyses = {}

if categories:
    category_map = {c.replace("_", " ").title(): c for c in categories}
    selected_label = st.sidebar.selectbox("Kategorie wählen:", list(category_map.keys()))
    selected_category = category_map[selected_label]
    selected_category_path = os.path.join(DATA_DIR, selected_category)
    
    all_pdf_paths = glob.glob(os.path.join(selected_category_path, "*.pdf"))
    for pdf_path in sorted(all_pdf_paths):
        party_name = os.path.basename(pdf_path).replace(".pdf", "")
        pages = get_pdf_page_count(pdf_path)
        selected_files.append((party_name, pdf_path, pages))
    
    precomputed_analyses = load_precomputed_analyses(selected_category_path)

# --- HEADER ---
st.markdown('<div class="title-text">> PDV V1.1</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Deep-Analysis von Parteiprogrammen</div>', unsafe_allow_html=True)

if selected_files:
    info_str = " | ".join([f"<b>{name}</b> ({pg} S.)" for name, _, pg in selected_files])
    st.markdown(f'<div class="pdf-info">Geladenes Parteien-Set: {info_str}</div>', unsafe_allow_html=True)
    active_g_files = get_cached_gemini_files(selected_files)
else:
    st.warning("Keine PDFs in dieser Kategorie gefunden.")

st.markdown("---")

if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = ""

# HOT TOPICS
if selected_files:
    st.markdown("### 🔥 Hot Topics")
    file_keys_tuple = tuple([(p[0], p[1], p[2]) for p in selected_files])
    auto_topics = get_hot_topics(file_keys_tuple, selected_category_path, api_key)
    
    cols = st.columns(min(len(auto_topics), 5))
    for idx, top_name in enumerate(auto_topics):
        if cols[idx % len(cols)].button(f"📌 {top_name}", key=f"ht_btn_{idx}DATA"):
            st.session_state.selected_topic = top_name

st.markdown("---")

# THEMEN-EINGABE & ANALYSE
st.markdown("### 📖 Thema analysieren")
topic = st.text_input("Thema eingeben oder oben ein Hot Topic anklicken:", value=st.session_state.selected_topic)

if st.button("ANALYSEN_STARTEN [ENTER]"):
    if not selected_files or not topic:
        st.warning("Bitte wähle ein Thema aus.")
    else:
        st.markdown("---")
        
        is_hot_topic = (topic in auto_topics)
        
        # Render-Hilfsfunktion für die neue Struktur
        def render_analysis_text(full_text):
            parts = full_text.split("## ")
            for part in parts:
                if not part.strip():
                    continue
                if part.startswith("📊"):
                    st.markdown("## 📊 " + part.replace("📊", ""))
                    continue
                    
                lines = part.split("\n")
                party_title = lines[0].strip()
                
                # Wir parsen die Bereiche für Maßnahmen sowie Chancen/Risiken
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
                
                # UI-Ausgabe Ebene 1: Partei
                st.markdown(f"### {party_title}")
                
                # Stichpunkt Maßnahmen + Aufklapper
                st.markdown(f"- **Detaillierte Maßnahmen:** {massnahme_summary}")
                with st.expander("➕ Mehr Details & Quellen zu Maßnahmen"):
                    st.markdown("\n".join(massnahme_details))
                
                # Stichpunkt Chancen + Aufklapper
                st.markdown(f"- **Chancen:** {chance_summary}")
                with st.expander("➕ Mehr Details & Quellen zu Chancen"):
                    st.markdown("\n".join(chance_details))
                
                # Stichpunkt Risiken + Aufklapper
                st.markdown(f"- **Risiken & Lücken:** {risiko_summary}")
                with st.expander("➕ Mehr Details & Quellen zu Risiken & Lücken"):
                    st.markdown("\n".join(risiko_details))
                
                st.markdown("---")

        if is_hot_topic and topic in precomputed_analyses:
            render_analysis_text(precomputed_analyses[topic])
        else:
            # Neuer strukturierter Prompt für die präzisen Stichpunkte + Detail-Blöcke
            prompt = f"""
            Vergleiche ausführlich und neutral die Vorhaben der Parteien zum Thema: {topic}
            
            REGELN:
            1. Nutze AUSSCHLIESSLICH Informationen aus den hochgeladenen Parteiprogrammen.
            2. Erstelle für jede Kategorie einen prägnanten Kurzsatz (Stichpunkt-Einleitung) und liefere dahinter im Detail-Block die tiefen Ausführungen inkl. Quellenangaben [Quelle: Dateiname.pdf, S. X].
            3. Falls eine Partei zu dem Thema keine Aussagen trifft, gib dies explizit an.

            Antworte strikt im folgenden Markdown-Format:

            ## [PARTEI NAME]
            **MASSNAHMEN_SUMMARY:** [Ein kurzer, aussagekräftiger Satz als Stichpunkt über die Hauptmaßnahmen]
            - **Detaillierte Vorhaben & Belege:**
              - Ausführliche Beschreibungpunkt 1 [Quelle: ...]
              - Ausführliche Beschreibungpunkt 2 [Quelle: ...]

            **CHANCEN_SUMMARY:** [Ein kurzer, aussagekräftiger Satz als Stichpunkt über die Hauptchancen]
            - **Detaillierte Potenziale & Belege:**
              - Ausführliche Analysepunkt 1 [Quelle: ...]

            **RISIKEN_SUMMARY:** [Ein kurzer, aussagekräftiger Satz als Stichpunkt über die Hauptrisiken/Lücken]
            - **Detaillierte Risiken, Lücken & Kritik:**
              - Ausführliche Analysepunkt 1 [Quelle: ...]

            ---
            ## 📊 FAZIT & VERGLEICHSTABELLE
            Erstelle eine übersichtliche Zusammenfassungstabelle zum direkten Vergleich aller gewählten Parteien:
            Partei | Kernforderung / Hauptmaßnahme | Erwartete Wirkung | Haupthürde / Risiko
            """

            response_text = None
            last_error = None

            with st.spinner(f"Führe Analyse für '{topic}' aus..."):
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
                render_analysis_text(response_text)

                if is_hot_topic:
                    save_analysis_to_json(selected_category_path, topic, response_text)
            else:
                st.error(f"Fehler bei der Generierung der Analyse: {last_error}")
