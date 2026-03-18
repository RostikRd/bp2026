# Výsledky evaluácie RAG agenta

Táto správa sumarizuje výsledky evaluácie RAG agenta zameraného na oblasť podporných opatrení a špeciálneho vzdelávania. Evaluácia prebehla **20. februára 2026** (timestamp 20260220_191145). Bolo vyhodnotených **30 otázok** v troch kategóriách: detekcia mimotématnych otázok (10), otázky zodpovedané z katalógu FAISS (10) a otázky zodpovedané výhradne z webových zdrojov (10). Hodnotenie odpovedí zabezpečoval LLM z kandidátov (Claude 3.5 Sonnet / Haiku alebo Claude Sonnet 4).


## 1. Off-topic detekcia (id 1–10)

Všetkých 10 otázok mimo témy podporných opatrení bolo agentom správne rozpoznaných ako mimotématne; na žiadnu z nich neposkytol obsahovú odpoveď z katalógu ani z webu.

| ID | Otázka | Výsledok |
|----|--------|----------|
| 1 | Aká bude zajtra počasie? | PASS |
| 2 | Ako uvariť bryndzové halušky? | PASS |
| 3 | Kedy začína futbalová liga? | PASS |
| 4 | Koľko obyvateľov má Bratislava? | PASS |
| 5 | Aké je hlavné mesto Francúzska? | PASS |
| 6 | Ako opraviť kvapkajúci kohútik v kúpeľni? | PASS |
| 7 | Odporuč mi dobrý film na večer. | PASS |
| 8 | Ako sa naučiť programovať v Pythone? | PASS |
| 9 | Koľko kalórií má pizza Margherita? | PASS |
| 10 | Kedy pristál človek na Mesiaci? | PASS |

**Presnosť: 10/10 (100 %).**

---

## 2. FAISS otázky – odpovede z katalógu (id 11–20)

Skóre podľa metrík faithfulness (Faith.), relevance (Relev.), context relevance (CtxRel.), correctness (Corr.) a completeness (Compl.) pre každú otázku (škála 1–5). Otázky sú skrátené na cca 60 znakov.

| ID | Otázka (skrátená)                                                        | Faith. | Relev. | CtxRel. | Corr. | Compl. |
|----|-------------------|--------|--------|---------|-------|--------|
| 11 | Žiak 2. ročníka s dyslexiou – podporné opatrenia úrovne 1 a 2?           | 4      | 5        | 3     | 5     | 5 |
| 12 | Žiak so ŠP má problémy s písomkami – ako upraviť hodnotenie (úroveň 2)?  | 5      | 5        | 4     | 5     | 4 |
| 13 | Ako podporiť žiaka s ASD pri zmene režimu a prechodoch?                  | 4      | 5        | 4     | 4     | 4 |
| 14 | Žiak s ADHD nevydrží 10 min sústredenia – opatrenia 1–3?                 | 4      | 5        | 4     | 4     | 4 |
| 15 | Aké podporné opatrenia pre žiaka s dysgrafiou v 3. ročníku?              | 4      | 4        | 5     | 4     | 4 |
| 16 | Žiak so sluchovým postihnutím v bežnej triede – opatrenia úrovne 2?      | 5      | 5        | 4     | 5     | 5 |
| 17 | Ako upraviť prostredie pre žiaka s hypersenzitivitou na hluk?            | 3      | 4        | 3     | 4     | 4 |
| 18 | Žiak s poruchou správania vyrušuje – opatrenia na úrovni 1?              | 4      | 4        | 5     | 4     | 4 |
| 19 | Aké sú rozdiely medzi úrovňami podporných opatrení 1, 2 a 3?             | 5      | 5        | 5     | 5     | 5 |
| 20 | Ako podporiť sociálno-komunikačné zručnosti žiaka s autizmom?            | 4      | 5        | 4     | 4     | 3 |
| **Priemer** |                                                             | **4,2** | **4,7** | **4,1** | **4,4** | **4,2** |

---

## 3. Web-only otázky – odpovede z internetu (id 21–30)

Pre otázky zodpovedané výhradne z webu sa nehodnotí faithfulness ani context relevance. Tabuľka uvádza relevance (Relev.), correctness (Corr.) a completeness (Compl.) v škále 1–5.

| ID | Otázka (skrátená)                                                | Relev. | Corr. | Compl. |
|----|-------------------|--------|-------|--------|
| 21 | Kontakt na ŠPÚ / NIVaM pre podporné opatrenia?                   | 5     | 4         | 4 |
| 22 | Kde nájsť aktuálny zoznam špeciálno-pedagogických centier?       | 4     | 4         | 3 |
| 23 | Čo hovorí novela školského zákona 2024 o podporných opatreniach? | 5     | 4         | 4 |
| 24 | Kde nájsť vzory IVP pre žiakov so špeciálnymi potrebami?         | 5     | 4         | 4 |
| 25 | Postup na podanie žiadosti o asistenta učiteľa?                  | 4     | 3         | 3 |
| 26 | Podmienky na zriadenie špeciálnej triedy v ZŠ podľa legislatívy? | 4     | 4         | 3 |
| 27 | Ako funguje systém poradenských zariadení (CPPPaP) po reforme?   | 5     | 4         | 4 |
| 28 | Aké finančné príspevky môže škola získať na podporné opatrenia?  | 4     | 3         | 3 |
| 29 | Aká je aktuálna vyhláška o podporných opatreniach?               | 5     | 4         | 4 |
| 30 | Aké práva majú rodičia žiaka so ŠVVP podľa legislatívy?          | 5     | 4         | 4 |
| **Priemer** |                                                      | **4,6** | **3,8** | **3,6** |

---

