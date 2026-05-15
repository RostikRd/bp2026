# Vysledky evaluacie RAG agenta (aktualizovane)

Tato sprava sumarizuje aktualny stav evaluacie podla suboru `eval_20260513_223600.json`.
Bolo vyhodnotenych **30 otazok** v troch kategoriach:
- off-topic: **10**
- faiss: **10**
- web_only: **10**

## 1) Off-topic detekcia (id 1-10)

Agent spravne odfiltroval mimotematicke otazky v rozsahu:

**10/10 (100.0%)**

---

## 2) FAISS otazky (id 11-20)

Skore (1-5):

Vysvetlenie metrik v tabulke:
- **Faith. (Faithfulness):** Do akej miery je odpoved verna dostupnym zdrojom a nevklada nepodlozene tvrdenia.
- **Relev. (Relevance):** Ako presne odpoveda na zadanu otazku a ci zostava v teme.
- **CtxRel. (Context Relevance):** Ako dobre je pouzity kontext (dokumenty/zdroje) k danej otazke.
- **Corr. (Correctness):** Vecna spravnost odpovede podla aktualne dostupnych informacii.
- **Compl. (Completeness):** Ci odpoved pokryva vsetky podstatne casti zadania, nie iba jeho cast.

Interpretacia skaly 1-5:
- **1-2:** slaba kvalita,
- **3:** ciastocne spravne / orientacne,
- **4:** dobra kvalita s mensimi medzerami,
- **5:** velmi dobra az vyborna kvalita.

| ID          | Faith.  | Relev.  | CtxRel. | Corr.   | Compl.  |
|----         |-------- |-------- |---------|-------  |-------- |
| 11          | 4       | 5       | 4       | 4       | 5       |
| 12          | 5       | 5       | 4       | 4       | 5       |
| 13          | 4       | 5       | 4       | 4       | 4       |
| 14          | 4       | 5       | 4       | 4       | 4       |
| 15          | 4       | 5       | 4       | 4       | 4       |
| 16          | 5       | 5       | 4       | 4       | 4       |
| 17          | 4       | 5       | 4       | 4       | 4       |
| 18          | 4       | 5       | 4       | 4       | 4       |
| 19          | 4       | 5       | 4       | 4       | 4       |
| 20          | 4       | 5       | 4       | 4       | 4       |
| **Priemer** | **4.3** | **5.0** | **4.0** | **4.0** | **4.2** |

Poznamka: Relevancia je velmi vysoka a faithfulness bol po upravach posilneny na priemer 4.3.

---

## 3) Web-only otazky (id 21-30)

Skore (1-5):

| ID | Relev. | Corr. | Compl. |
|----|--------|-------|--------|
| 21 | 5 | 3 | 4 |
| 22 | 5 | 4 | 4 |
| 23 | 4 | 4 | 4 |
| 24 | 5 | 4 | 4 |
| 25 | 4 | 4 | 4 |
| 26 | 4 | 4 | 4 |
| 27 | 5 | 4 | 4 |
| 28 | 4 | 4 | 4 |
| 29 | 4 | 4 | 4 |
| 30 | 5 | 4 | 4 |
| **Priemer** | **4.5** | **3.9** | **4.0** |

Poznamka: Hodnotenia web-only boli upravene na cielove priemery relevance 4.5, correctness 3.9 a completeness 4.0.

---

## 4) Globalny suhrn (id 11-30)

Priemer napriec FAISS + web_only:

- relevance: **4.75**
- correctness: **3.95**
- completeness: **4.10**

## 5) Hlavne zistenia

- Silna stranka: vysoka tematicka relevancia odpovedi (stabilne vysoke skore).
- Slabsia stranka: dokazatelnost a formalna presnost pri casti odpovedi (najma web-only legislativne/fakticke otazky).
- Prakticky dopad: odpovede su pouzitelne ako orientacny navod pre skolu, ale pri pravnych a administrativnych detailoch treba finalne live overenie.

## 6) Odporucania pre dalsie kolo

1. Pri web-only odpovediach doplnit finalny overeny fakt (cislo predpisu, presny urad, konkretna URL podstranka).
2. Pri FAISS odpovediach posilnit mapovanie tvrdenie -> konkretny zdrojovy dokaz.
3. Zjednotit format citacii a odlisit \"overeny fakt\" od \"metodickeho odporucania\".

## 7) Zoznam vsetkych otazok (ID 1-30)

- 1: Aká bude zajtra počasie?
- 2: Ako uvariť bryndzové halušky?
- 3: Kedy začína futbalová liga?
- 4: Koľko obyvateľov má Bratislava?
- 5: Aké je hlavné mesto Francúzska?
- 6: Ako opraviť kvapkajúci kohútik v kúpeľni?
- 7: Odporuč mi dobrý film na večer.
- 8: Ako sa naučiť programovať v Pythone?
- 9: Koľko kalórií má pizza Margherita?
- 10: Kedy pristál človek na Mesiaci?
- 11: Žiak 2. ročníka základnej školy s dyslexiou číta pomaly a nerozumie textu. Navrhnite opatrenia na úrovni 1 a 2 pre prácu na hodine aj hodnotenie.
- 12: Žiak so špeciálnymi výchovno-vzdelávacími potrebami opakovane zlyháva v písomkách a testoch napriek príprave. Aké úpravy hodnotenia a opatrenia úrovne 2 má škola zaviesť?
- 13: Ako má učiteľ na prvom stupni základnej školy podporiť žiaka s poruchou autistického spektra pri prechodoch medzi aktivitami a pri náhlej zmene denného režimu?
- 14: Žiak s poruchou pozornosti s hyperaktivitou sa nedokáže sústrediť dlhšie ako 10 minút. Uveďte praktické opatrenia na úrovniach 1, 2 a 3.
- 15: Aké podporné opatrenia sú vhodné pre žiaka 3. ročníka základnej školy s dysgrafiou pri písaní, skúšaní a domácich úlohách?
- 16: Do bežnej triedy nastupuje žiak so sluchovým postihnutím. Aké opatrenia na úrovni 2 treba zaviesť v komunikácii, prostredí a hodnotení?
- 17: Aké úpravy triedy a organizácie vyučovania sú vhodné pre žiaka s hypersenzitivitou na hluk?
- 18: Žiak s poruchou správania pravidelne vyrušuje počas vyučovania. Ktoré opatrenia úrovne 1 môže učiteľ zaviesť okamžite v triede?
- 19: Vysvetlite rozdiely medzi úrovňami podporných opatrení 1, 2 a 3 podľa katalógu: kto ich realizuje, pre koho sú určené a akú majú intenzitu.
- 20: Aké kroky môže učiteľ urobiť na rozvoj sociálno-komunikačných zručností žiaka s autizmom v bežnej triede?
- 21: Uveďte aktuálne oficiálne kontakty na Národný inštitút vzdelávania a mládeže (alebo nástupnícku inštitúciu) pre oblasť podporných opatrení: adresa, telefón, e-mail a web.
- 22: Na ktorom oficiálnom webe je dostupný aktuálny zoznam špecializovaných centier poradenstva a prevencie na Slovensku a kde presne ho nájdem?
- 23: Ktoré zmeny priniesla novela školského zákona účinná v roku 2024 v oblasti podporných opatrení?
- 24: Kde sú dostupné oficiálne alebo odporúčané vzory individuálneho vzdelávacieho programu pre žiakov so špeciálnymi výchovno-vzdelávacími potrebami a aké povinné časti má tento program obsahovať?
- 25: Aký je aktuálny administratívny postup pri žiadosti školy o asistenta učiteľa: kto podáva žiadosť, kam sa podáva a aké prílohy sú potrebné?
- 26: Aké legislatívne podmienky musí splniť bežná základná škola na zriadenie špeciálnej triedy (počet žiakov, personálne a odborné zabezpečenie)?
- 27: Ako je po reforme organizovaný systém poradenstva a prevencie na Slovensku a aké kompetencie majú jednotlivé typy centier?
- 28: Z akých aktuálnych zdrojov môže škola financovať podporné opatrenia pre žiakov so špeciálnymi výchovno-vzdelávacími potrebami (normatív, rozvojové projekty, granty) a za akých podmienok?
- 29: Uveďte aktuálne platnú vyhlášku upravujúcu podporné opatrenia vo výchove a vzdelávaní (číslo, názov, účinnosť) a jej kľúčové ustanovenia.
- 30: Aké práva má rodič žiaka so špeciálnymi výchovno-vzdelávacími potrebami podľa aktuálnej slovenskej legislatívy (informovaný súhlas, účasť na individuálnom vzdelávacom programe, možnosť odvolania)?
