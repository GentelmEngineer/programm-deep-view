import os
import json
import time
from google import genai

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("FEHLER: Bitte setze zuerst den GEMINI_API_KEY.")
    exit(1)

client = genai.Client(api_key=api_key)
DATA_DIR = "data"

def get_analysis_prompt(topic):
    return f"""
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

def precompute():
    if not os.path.exists(DATA_DIR):
        print(f"Ordner {DATA_DIR} nicht gefunden.")
        return

    categories = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]
    
    for cat in categories:
        cat_path = os.path.join(DATA_DIR, cat)
        pdf_paths = [os.path.join(cat_path, f) for f in os.listdir(cat_path) if f.endswith(".pdf")]
        
        if not pdf_paths:
            continue
            
        print(f"\n======================================")
        print(f"Verarbeite Kategorie: {cat}")
        print(f"======================================")
        
        uploaded_files = []
        for path in pdf_paths:
            print(f"Lade PDF hoch: {os.path.basename(path)}...")
            g_file = client.files.upload(file=path)
            uploaded_files.append(g_file)
            
        # 1. Hot Topics ermitteln
        print("Ermittle Hot Topics...")
        ht_prompt = "Nenne 5-7 prägnante Hauptthemen/Schlagwörter dieser Parteiprogramme. Gib NUR eine kommaseparierte Liste zurück (z.B. Klimaschutz, Steuern, Rente)."
        
        topics = ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"]
        try:
            res = client.models.generate_content(model="gemini-2.5-flash", contents=[*uploaded_files, ht_prompt])
            if res and res.text:
                topics = [t.strip() for t in res.text.split(",") if t.strip()]
        except Exception as e:
            print(f"Fehler bei Hot Topics: {e}")
            
        # Hot Topics als Liste speichern
        json_path = os.path.join(cat_path, "hot_topics.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
        print(f"Hot Topics gespeichert: {topics}")
        
        # 2. Für JEDES Hot Topic direkt die Analyse generieren und abspeichern
        analyses = {}
        for topic in topics:
            print(f"--> Generiere Analyse für Hot Topic: '{topic}'...")
            analysis_prompt = get_analysis_prompt(topic)
            
            analysis_text = None
            for model_name in ["gemini-2.5-flash", "gemini-3.5-flash-lite"]:
                try:
                    res = client.models.generate_content(model=model_name, contents=[*uploaded_files, analysis_prompt])
                    if res and res.text:
                        analysis_text = res.text
                        break
                except Exception as e:
                    print(f"Versuch mit {model_name} fehlgeschlagen: {e}")
                    time.sleep(2)
            
            if analysis_text:
                analyses[topic] = analysis_text
            else:
                analyses[topic] = "Analysedaten konnten nicht automatisch generiert werden."
            
            time.sleep(1) # Kurze Pause gegen API-Limits
            
        # Analysen in einer JSON-Datei speichern
        analyses_json_path = os.path.join(cat_path, "hot_topic_analyses.json")
        with open(analyses_json_path, "w", encoding="utf-8") as f:
            json.dump(analyses, f, ensure_ascii=False, indent=2)
        print(f"Alle Analysen erfolgreich gespeichert in: {analyses_json_path}")
        
        # Gemini-Files aufräumen
        for g_file in uploaded_files:
            try:
                client.files.delete(name=g_file.name)
            except:
                pass

if __name__ == "__main__":
    precompute()
