import os
import glob
import streamlit as st
from google import genai

# Design & Layout Setup
st.set_page_config(page_title="Programm Deep View", page_icon="⚡", layout="wide")

# CSS für den Hacker-/Terminal-Look (vollständig geschlossen)
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Courier New', Courier, monospace !important; }
    .title-text { font-size: 2.2rem; font-weight: 700; color: #00FF66; margin-bottom: 0px; }
    .sub-text { color: #8B949E; font-size: 0.9rem; margin-bottom: 20px; }
    .stButton>button { background-color: #238636 !important; color: #ffffff !important; border: 1px solid #2EA043 !important; width: 100%; }
</style>
""", unsafe_allow_html=True)

# API-Key laden
api_key = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("FEHLER: Der Schlüssel (GEMINI_API_KEY) fehlt noch in den Einstellungen!")
    st.stop()

# ClientWelcher Code ist gemeint und wo gab es vorher ein Problem? 

Bitte poste den bisherigen Code oder beschreibe kurz, was das Skript tun soll – dann erstelle ich dir sofort eine funktionierende Version!
