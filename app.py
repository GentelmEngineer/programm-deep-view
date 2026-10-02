import os
import json
import glob
import streamlit as st
from google import genai
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
    
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: transparent; color: #8B949E; text-align: right; padding-right: 20px; font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("FEHLER: GEMINI_API_KEY fehlt!")
    st.stop()

client = genai.Client(api_key=api_key)
DATA_DIR = "data"

MODELS_TO_TRY = [
    "gemini-3.5-flash-lite",
"gemini-3.8-flash"

def get_pdf_page_count(filepath):
    try:
        reader = pypdf.PdfReader(filepath)
        return len(reader.pages)
    except Exception:
        return "?"

# --- PERSISTENTES CLOUD-DATEI-CACHING (Verhindert erneutes Hochladen) ---
def get_cached_gemini_files(file_tuples, category_path):
    cache_path = os.path.join(category_path, "gemini_files_cache.json")
    cloud_file_map = {}
    
    # Versuche bestehenden Cloud-Cache zu laden
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
        
        # Prüfen, ob die Datei bereits in der Cloud registriert ist und existiert
        if file_basename in cloud_file_map:
            remote_name = cloud_file_map[file_basename]
            try:
                # Testen, ob das File noch in der Gemini Cloud existiert
                g_file = client.files.get(name=remote_name)
            except Exception:
                g_file = None # Wurde in der Cloud gelöscht / abgelaufen

        # Wenn nicht vorhanden, einmalig hochladen
        if not g_file:
            with st.spinner(f"Lade '{party_name}' einmalig in die Gemini-Cloud hoch..."):
                g_file = client.files.upload(file=pdf_path)
                cloud_file_map[file_basename] = g_file.name
                updated = True

        gemini_files.append(g_file)

    # Cache aktualisieren, falls neue Dateien hochgeladen wurden
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

    temp_client = genai.Client(api_key=_api_key)
    fallback_topics = ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]
    if not active_g_files:
        return fallback_topics
    
    prompt = "Nenne exakt 5 prägnante Hauptthemen/Schlagwörter dieser Parteiprogramme. Gib NUR eine kommaseparierte Liste zurück."
    
    generated_topics = None
    for model_name in MODELS_TO_TRY:
        try:
            res = temp_client.models.generate_content(
                model=model_name,
                contents=[*active_g_files, prompt]
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

# --- HEADER & TITEL ---
st.markdown("""
<div class="title-box">
    <div class="title-text">VoteCore</div>
    <div class="sub-text">Deep-Analysis von Parteiprogrammen</div>
</div>
""", unsafe_allow_html=True)

# --- WAHLORDNER / KATEGORIE AUSWAHL OBEN ---
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
    # Nutzt jetzt den persistenten Cloud-Cache für die Dateien
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

if st.button("Starte die Analyse"):
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
                if part.startswith("📊"):
                    st.markdown("## 📊 " + part.replace("📊", ""))
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
                
                st.markdown(f"- **Detaillierte Maßnahmen:** {massnahme_summary}")
                with st.expander("➕ Mehr Details & Quellen zu Maßnahmen"):
                    st.markdown("\n".join(massnahme_details))
                
                st.markdown(f"- **Chancen:** {chance_summary}")
                with st.expander("➕ Mehr Details & Quellen zu Chancen"):
                    st.markdown("\n".join(chance_details))
                
                st.markdown(f"- **Risiken & Lücken:** {risiko_summary}")
                with st.expander("➕ Mehr Details & Quellen zu Risiken & Lücken"):
                    st.markdown("\n".join(risiko_details))
                
                st.markdown("---")

        if is_hot_topic and topic in precomputed_analyses:
            render_analysis_text(precomputed_analyses[topic])
        else:
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

# --- FUßNOTE MIT VERSION ---
st.markdown('<div class="footer">VoteCore V1.1</div>', unsafe_allow_html=True)
