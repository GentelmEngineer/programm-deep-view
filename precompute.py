import os
import json
from google import genai
import pypdf

# API Key prüfen
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("FEHLER: Bitte setze die Umgebungsvariable GEMINI_API_KEY.")
    exit(1)

client = genai.Client(api_key=api_key)
DATA_DIR = "data"

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
            
        print(f"\n--- Verarbeite Kategorie: {cat} ---")
        
        # PDFs für diesen Durchlauf hochladen
        uploaded_files = []
        for path in pdf_paths:
            print(f"Lade hoch: {os.path.basename(path)}...")
            g_file = client.files.upload(file=path)
            uploaded_files.append(g_file)
            
        # Hot Topics generieren
        print("Generiere Hot Topics via Gemini...")
        prompt = "Nenne 5-7 prägnante Hauptthemen/Schlagwörter dieser Parteiprogramme. Gib NUR eine kommaseparierte Liste zurück (z.B. Klimaschutz, Steuern, Rente)."
        
        topics = ["Klimaschutz", "Steuern", "Digitalisierung", "Rente", "Mieten"] # Fallback
        try:
            res = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[*uploaded_files, prompt]
            )
            if res and res.text:
                topics = [t.strip() for t in res.text.split(",") if t.strip()]
        except Exception as e:
            print(f"Fehler bei API-Abfrage: {e}")
            
        # In JSON-Datei im Kategorie-Ordner speichern
        json_path = os.path.join(cat_path, "hot_topics.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
            
        print(f"Gespeichert: {json_path} -> {topics}")
        
        # Optional: Aufgeräumte Gemini-Files gleich wieder löschen
        for g_file in uploaded_files:
            try:
                client.files.delete(name=g_file.name)
            except:
                pass

if __name__ == "__main__":
    precompute()
