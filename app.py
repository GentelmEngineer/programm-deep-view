else:
            prompt = f"""
            Analysiere neutral die Vorhaben der Parteien zum Thema: {topic}.

            WICHTIGE REGELN:
            1. Für die **Maßnahmen**: Nutze AUSSCHLIESSLICH die hochgeladenen Parteiprogramme. Keine externen Quellen. Jede Maßnahme braucht eine exakte Quellenangabe [Quelle: Dateiname.pdf, S. X].
            2. Für die **Chancen** und **Risiken/Umsetzung**: Du darfst hier neben den Programmen auch fundiertes Expertenwissen, ökonomische/wissenschaftliche Einschätzungen und allgemeine Analysen zu den Konsequenzen einbeziehen (z.B. reale Hürden, Haushaltskonsequenzen oder Expertenstimmen).

            Beschränke dich pro Kategorie auf exakt die 3 wesentlichen Punkte.

            Antworte strikt im folgenden Format:

            ## [PARTEI NAME]
            **MASSNAHMEN_SUMMARY:** [Kurzer Satz zur Hauptmaßnahme aus dem Programm]
            - **Detaillierte Vorhaben & Belege:**
              - 1. ... [Quelle: ...]
              - 2. ... [Quelle: ...]
              - 3. ... [Quelle: ...]

            **CHANCEN_SUMMARY:** [Kurzer Satz zur Hauptchance / Potenzial]
            - **Detaillierte Potenziale & Experten-Sicht:**
              - 1. ...
              - 2. ...
              - 3. ...

            **RISIKEN_SUMMARY:** [Kurzer Satz zum Hauptrisiko / Umsetzbarkeit]
            - **Detaillierte Risiken & Lücken:**
              - 1. ...
              - 2. ...
              - 3. ...
            """
