import os
import glob
import streamlit as st
from google import genai

# Design & Layout Setup
st.set_page_config(page_title="Programm Deep View", page_icon="⚡", layout="wide")

# CSS für den Hacker-/Terminal-Look
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !importantUm genau zu sagen, ob Ihr Code Informationen ausgibt, die nicht im PDF stehen, müsste ich den Code sehen. 

Es gibt aber ein sehr bekanntes Phänomen bei der Arbeit mit PDFs und KI (wie Chatbots oder LLMs): das sogenannte **Halluzinieren**.

---

### Wann gibt Ihr Code Informationen aus, die *nicht* im PDF stehen?

1. **Sie nutzen RAG (Retrieval-Augmentation) ohne strenge Prompt-Regeln:**
   Wenn Ihr Code Abschnitte aus dem PDF an ein Sprachmodell schickt, verwendet das Modell oft sein eigenes Allgemeinwissen, um Lücken zu füllen.

2. **Das PDF wird nicht richtig ausgelesen:**
   Wenn der Text im PDF als Bild/Scan vorliegt (ohne OCR) oder Tabellen verzerrt extrahiert werden, fehlt dem Modell der Kontext – es "erfindet" dann passende Antworten.

3. **Der Prompt verbietet externes Wissen nicht:**
   Standardmäßig versuchen KI-Modelle immer, eine hilfreiche Antwort zu geben, selbst wenn die Information im übergebenen Text fehlt.

---

### Wie verhindern Sie das im Code?

Wenn Sie verhindern möchten, dass der Code externe Informationen verwendet, passen Sie den **System-Prompt** an das KI-Modell an:

```text
Du bist ein Assistent, der Fragen AUSSCHLIESSLICH auf Basis des bereitgestellten PDF-Kontexts beantwortet.
Wenn die Antwort nicht explizit im Text enthalten ist, antworte genau mit: 
"Diese Information ist im bereitgestellten Dokument nicht enthalten."
Nutze unter keinen Umständen dein eigenes Allgemeinwissen.
