# Аналіз проекту та рекомендації щодо реалізації нових функцій

## 📋 Загальний огляд проекту

**Назва проекту:** BP2026 - Inteligentný agent pre podporu práce špeciálneho pedagóga

**Тип:** RAG (Retrieval-Augmented Generation) система для консультацій у сфері освітньої підтримки на Словаччині

**Поточна архітектура:**
- **Frontend:** HTML + JavaScript (ui/index.html, ui/js/main.js)
- **Backend:** FastAPI (app.py)
- **RAG Engine:** LangChain + FAISS (src/rag/ask_cli.py)
- **Джерела даних:** Каталог підтримних заходів з podporneopatrenia.minedu.sk

---

## 🎯 Аналіз вимог викладача та рекомендації щодо реалізації

### 1. Agent môže využiť internet ak nenájde výsledky v dokumentoch

#### Поточний стан
- Система працює виключно з локальною векторною базою даних (FAISS)
- Відсутня можливість пошуку в інтернеті
- Відповіді генеруються тільки на основі документів з `rag_index/faiss_e5/`

#### Рекомендації щодо реалізації

**Варіант A: Інтеграція з пошуковими API (рекомендовано)**

1. **Використання Tavily API або Serper API**
   - Tavily API спеціалізований для RAG систем
   - Serper API - швидкий та ефективний Google Search API
   - Альтернатива: Bing Search API, Google Custom Search API

2. **Архітектура рішення:**
   ```
   Запит користувача
   ↓
   Пошук у локальній базі (FAISS)
   ↓
   Оцінка релевантності результатів (threshold)
   ↓
   Якщо релевантність < threshold → Пошук в інтернеті
   ↓
   Об'єднання результатів (локальні + інтернет)
   ↓
   Генерація відповіді через LLM
   ```

3. **Технічна реалізація:**

   **Додати до `requirements.txt`:**
   ```python
   tavily-python>=0.3.0
   # або
   google-search-results>=2.4.2  # для Serper
   ```

   **Створити новий модуль `src/rag/web_search.py`:**
   ```python
   import os
   from typing import List, Dict
   from tavily import TavilyClient
   
   def search_web(query: str, max_results: int = 5) -> List[Dict]:
       """Пошук в інтернеті через Tavily API"""
       api_key = os.environ.get("TAVILY_API_KEY", "")
       if not api_key:
           return []
       
       client = TavilyClient(api_key=api_key)
       results = client.search(
           query=query,
           search_depth="advanced",
           max_results=max_results,
           include_answer=True
       )
       
       return [
           {
               "title": r.get("title", ""),
               "url": r.get("url", ""),
               "content": r.get("content", ""),
               "score": r.get("score", 0.0)
           }
           for r in results.get("results", [])
       ]
   ```

   **Модифікувати `src/rag/ask_cli.py`:**
   ```python
   def ask(query: str, use_web_fallback: bool = True) -> str:
       vs = get_vectorstore()
       docs_all = vs.similarity_search(query, k=20)
       
       # Оцінка релевантності результатів
       if docs_all:
           # Отримуємо similarity scores
           docs_with_scores = vs.similarity_search_with_score(query, k=20)
           avg_score = sum(score for _, score in docs_with_scores) / len(docs_with_scores)
           
           # Якщо середня релевантність низька, шукаємо в інтернеті
           if use_web_fallback and avg_score < 0.7:  # threshold
               from src.rag.web_search import search_web
               web_results = search_web(query, max_results=5)
               
               # Додаємо веб-результати до контексту
               for web_doc in web_results:
                   # Створюємо Document об'єкт для сумісності
                   from langchain_core.documents import Document
                   web_doc_obj = Document(
                       page_content=web_doc["content"],
                       metadata={
                           "title": web_doc["title"],
                           "url": web_doc["url"],
                           "source": "web"
                       }
                   )
                   docs_all.append(web_doc_obj)
       
       # Продовжуємо з існуючою логікою...
   ```

4. **Конфігурація:**
   - Додати `TAVILY_API_KEY` до `api_keys.env` та `docker/.env`
   - Додати параметр `USE_WEB_FALLBACK=true` для контролю функції

**Варіант B: Використання LangChain Web Search Tools**

```python
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import initialize_agent, AgentType

search = DuckDuckGoSearchRun()

# Використання в agent
agent = initialize_agent(
    tools=[search],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)
```

**Переваги Варіанту A:**
- ✅ Більш контрольований пошук
- ✅ Краща інтеграція з RAG pipeline
- ✅ Можливість фільтрації результатів
- ✅ Краща якість результатів (Tavily оптимізований для RAG)

---

### 2. Agent môže overiť výsledky pomocným vyhľadávaním

#### Поточний стан
- Система не перевіряє результати додатковим пошуком
- Відсутня валідація відповідей

#### Рекомендації щодо реалізації

**Архітектура рішення:**

1. **Двоетапний процес перевірки:**
   ```
   Генерація початкової відповіді
   ↓
   Витяг ключових тверджень/фактів
   ↓
   Перевірка кожного твердження через пошук
   ↓
   Оновлення відповіді з позначками валідації
   ```

2. **Технічна реалізація:**

   **Створити модуль `src/rag/verification.py`:**
   ```python
   from typing import List, Dict
   import re
   from src.rag.web_search import search_web
   from langchain_anthropic import ChatAnthropic
   
   def extract_claims(text: str) -> List[str]:
       """Витяг ключових тверджень з тексту"""
       # Використовуємо LLM для витягу тверджень
       llm = ChatAnthropic(model="claude-3-5-haiku-20241022", temperature=0)
       prompt = f"""Витягни ключові фактичні твердження з наступного тексту.
       Поверни тільки список тверджень, по одному на рядок:
       
       {text}
       """
       response = llm.invoke(prompt)
       claims = [c.strip() for c in response.content.split('\n') if c.strip()]
       return claims
   
   def verify_claim(claim: str, original_docs: List) -> Dict:
       """Перевірка одного твердження"""
       # Пошук в оригінальних документах
       claim_lower = claim.lower()
       found_in_docs = any(
           claim_lower in doc.page_content.lower() 
           for doc in original_docs
       )
       
       # Якщо не знайдено, шукаємо в інтернеті
       if not found_in_docs:
           web_results = search_web(claim, max_results=3)
           found_in_web = len(web_results) > 0
           return {
               "claim": claim,
               "verified_in_docs": False,
               "verified_in_web": found_in_web,
               "web_sources": [r["url"] for r in web_results] if found_in_web else []
           }
       
       return {
           "claim": claim,
           "verified_in_docs": True,
           "verified_in_web": False,
           "web_sources": []
       }
   
   def verify_response(response: str, original_docs: List) -> str:
       """Перевірка всієї відповіді"""
       claims = extract_claims(response)
       verifications = [verify_claim(claim, original_docs) for claim in claims]
       
       # Додаємо індикатори валідації до відповіді
       verified_sections = []
       for v in verifications:
           if v["verified_in_docs"]:
               status = "✅ Перевірено в документах"
           elif v["verified_in_web"]:
               status = f"⚠️ Перевірено в інтернеті: {', '.join(v['web_sources'][:2])}"
           else:
               status = "❓ Потребує додаткової перевірки"
           
           verified_sections.append(f"- {v['claim']} - {status}")
       
       if verified_sections:
           response += "\n\n## ✅ Перевірка фактів\n" + "\n".join(verified_sections)
       
       return response
   ```

   **Інтеграція в `ask_cli.py`:**
   ```python
   def ask(query: str, verify_results: bool = True) -> str:
       # ... існуюча логіка генерації відповіді ...
       
       result = "\n".join(result_parts)
       
       # Перевірка результатів
       if verify_results:
           from src.rag.verification import verify_response
           result = verify_response(result, docs)
       
       return result
   ```

3. **Альтернативний підхід - Self-RAG:**
   - Використання Self-RAG архітектури, де модель сама вирішує, коли потрібен додатковий пошук
   - Більш складне, але більш ефективне рішення

---

### 3. Možnosť spätnej väzby od pedagóga

#### Поточний стан
- Відсутня система збору зворотного зв'язку
- Немає збереження історії запитів
- Немає можливості оцінити якість відповіді

#### Рекомендації щодо реалізації

**Архітектура рішення:**

1. **База даних для зберігання:**
   - Використання SQLite для простоти (або PostgreSQL для production)
   - Таблиці: `queries`, `responses`, `feedback`

2. **Структура бази даних:**

   **Створити `src/db/schema.sql`:**
   ```sql
   CREATE TABLE IF NOT EXISTS queries (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       question TEXT NOT NULL,
       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
       user_id TEXT
   );
   
   CREATE TABLE IF NOT EXISTS responses (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       query_id INTEGER,
       answer TEXT NOT NULL,
       sources TEXT,  -- JSON array
       FOREIGN KEY (query_id) REFERENCES queries(id)
   );
   
   CREATE TABLE IF NOT EXISTS feedback (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       response_id INTEGER,
       rating INTEGER,  -- 1-5
       comment TEXT,
       useful BOOLEAN,
       accurate BOOLEAN,
       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (response_id) REFERENCES responses(id)
   );
   ```

3. **Backend реалізація:**

   **Створити `src/db/database.py`:**
   ```python
   import sqlite3
   from pathlib import Path
   from datetime import datetime
   from typing import Optional, Dict, List
   
   DB_PATH = Path("data/feedback.db")
   DB_PATH.parent.mkdir(exist_ok=True)
   
   def get_db():
       conn = sqlite3.connect(str(DB_PATH))
       conn.row_factory = sqlite3.Row
       return conn
   
   def save_query(question: str, user_id: Optional[str] = None) -> int:
       conn = get_db()
       cursor = conn.cursor()
       cursor.execute(
           "INSERT INTO queries (question, user_id) VALUES (?, ?)",
           (question, user_id)
       )
       query_id = cursor.lastrowid
       conn.commit()
       conn.close()
       return query_id
   
   def save_response(query_id: int, answer: str, sources: List[Dict]) -> int:
       conn = get_db()
       cursor = conn.cursor()
       import json
       cursor.execute(
           "INSERT INTO responses (query_id, answer, sources) VALUES (?, ?, ?)",
           (query_id, answer, json.dumps(sources))
       )
       response_id = cursor.lastrowid
       conn.commit()
       conn.close()
       return response_id
   
   def save_feedback(response_id: int, rating: int, comment: str = "", 
                     useful: bool = None, accurate: bool = None):
       conn = get_db()
       cursor = conn.cursor()
       cursor.execute(
           """INSERT INTO feedback (response_id, rating, comment, useful, accurate)
              VALUES (?, ?, ?, ?, ?)""",
           (response_id, rating, comment, useful, accurate)
       )
       conn.commit()
       conn.close()
   ```

4. **API endpoints:**

   **Додати до `app.py`:**
   ```python
   from src.db.database import save_query, save_response, save_feedback
   from pydantic import BaseModel
   
   class FeedbackRequest(BaseModel):
       response_id: int
       rating: int  # 1-5
       comment: str = ""
       useful: bool = None
       accurate: bool = None
   
   @app.post("/api/feedback")
   def submit_feedback(feedback: FeedbackRequest):
       save_feedback(
           feedback.response_id,
           feedback.rating,
           feedback.comment,
           feedback.useful,
           feedback.accurate
       )
       return {"status": "success"}
   
   @app.post("/api/ask")
   def ask(q: Q):
       # Зберігаємо запит
       query_id = save_query(q.question)
       
       # Генеруємо відповідь
       answer = run_ai(q.question)
       
       # Парсимо джерела з відповіді
       sources = extract_sources_from_answer(answer)
       
       # Зберігаємо відповідь
       response_id = save_response(query_id, answer, sources)
       
       return {
           "answer": answer,
           "response_id": response_id  # Для подальшого feedback
       }
   ```

5. **Frontend реалізація:**

   **Додати до `ui/index.html` (після відповіді):**
   ```html
   <div class="feedback-section" id="feedback-section" style="display: none;">
     <h3>Ваша оцінка відповіді:</h3>
     <div class="rating-buttons">
       <button class="rating-btn" data-rating="1">⭐</button>
       <button class="rating-btn" data-rating="2">⭐⭐</button>
       <button class="rating-btn" data-rating="3">⭐⭐⭐</button>
       <button class="rating-btn" data-rating="4">⭐⭐⭐⭐</button>
       <button class="rating-btn" data-rating="5">⭐⭐⭐⭐⭐</button>
     </div>
     <div class="feedback-options">
       <label>
         <input type="checkbox" id="useful"> Корисна відповідь
       </label>
       <label>
         <input type="checkbox" id="accurate"> Точна відповідь
       </label>
     </div>
     <textarea id="feedback-comment" placeholder="Додаткові коментарі (необов'язково)"></textarea>
     <button id="submit-feedback">Відправити відгук</button>
   </div>
   ```

   **Додати до `ui/js/main.js`:**
   ```javascript
   let currentResponseId = null;
   
   async function submitQuestion() {
       // ... існуючий код ...
       
       const data = await response.json();
       currentResponseId = data.response_id;  // Зберігаємо ID
       
       // Показуємо секцію feedback
       document.getElementById('feedback-section').style.display = 'block';
       
       // ... решта коду ...
   }
   
   document.getElementById('submit-feedback').addEventListener('click', async () => {
       const rating = document.querySelector('.rating-btn.selected')?.dataset.rating;
       const comment = document.getElementById('feedback-comment').value;
       const useful = document.getElementById('useful').checked;
       const accurate = document.getElementById('accurate').checked;
       
       if (!rating || !currentResponseId) return;
       
       await fetch('/api/feedback', {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           body: JSON.stringify({
               response_id: currentResponseId,
               rating: parseInt(rating),
               comment,
               useful,
               accurate
           })
       });
       
       alert('Дякуємо за ваш відгук!');
       document.getElementById('feedback-section').style.display = 'none';
   });
   ```

6. **Додаткові можливості:**
   - Статистика feedback для адміністраторів
   - Автоматичне покращення на основі feedback
   - Експорт feedback для аналізу

---

### 4. Zlepšite vysvetliteľnosť výsledkov agenta

#### Поточний стан
- Система вже додає джерела в кінці відповіді
- Відсутнє пояснення, чому саме ці заходи були обрані
- Немає посилань на законодавство

#### Рекомендації щодо реалізації

1. **Покращення системного промпту:**

   **Модифікувати `system_prompt` в `ask_cli.py`:**
   ```python
   system_prompt = """...існуючий текст...
   
   VYSVETLITEĽNOSŤ:
   - Pre každé navrhnuté opatrenie vysvetli PREČO bolo vybrané
   - Uveď konkrétne potreby žiaka, ktoré toto opatrenie rieši
   - Odkaž na relevantné sekcie dokumentov
   - Ak je relevantné, odkaž na legislatívu (zákon, vyhláška)
   
   FORMÁT ODPOVEDE:
   ## 🎯 Analýza problému
   ...
   
   ## 📋 Konkrétne opatrenia
   ### [Názov opatrenia]
   **Prečo toto opatrenie:**
   - Konkrétny dôvod výberu
   - Potreby žiaka, ktoré rieši
   
   **Realizácia:**
   - [Učiteľ] Konkrétna činnosť
   
   **Odkazy:**
   - 📄 [Názov dokumentu](URL) - sekcia "Názov sekcie"
   - ⚖️ Zákon č. XXX/YYYY - § XX (ak relevantné)
   
   ## ⚖️ Legislatívne základy
   - Zákon č. 245/2008 Z. z. o výchove a vzdelávaní...
   - Vyhláška č. 322/2008 Z. z. o...
   """
   ```

2. **Додавання посилань на законодавство:**

   **Створити `src/rag/legislation.py`:**
   ```python
   LEGISLATION_REFERENCES = {
       "podporné opatrenia": {
           "law": "Zákon č. 245/2008 Z. z. o výchove a vzdelávaní",
           "url": "https://www.slov-lex.sk/pravne-predpisy/SK/ZZ/2008/245/",
           "sections": ["§ 2", "§ 3"]
       },
       "hodnotenie": {
           "law": "Vyhláška č. 322/2008 Z. z.",
           "url": "https://www.slov-lex.sk/...",
           "sections": ["§ 15"]
       },
       # Додати більше посилань
   }
   
   def find_relevant_legislation(query: str, suggested_measures: List[str]) -> List[Dict]:
       """Знаходить релевантне законодавство"""
       relevant = []
       query_lower = query.lower()
       
       for key, ref in LEGISLATION_REFERENCES.items():
           if key in query_lower or any(key in measure.lower() for measure in suggested_measures):
               relevant.append(ref)
       
       return relevant
   ```

3. **Покращення форматування джерел:**

   **Модифікувати секцію джерел в `ask_cli.py`:**
   ```python
   # Замість простого списку
   result_parts.append("\n## 📚 Zdroje a odkazy\n")
   
   # Групування джерел за типом
   result_parts.append("### 📄 Dokumenty podporných opatrení")
   for source in sources_info:
       if source["url"]:
           result_parts.append(
               f"- [{source['num']}] **{source['title']}**  \n"
               f"  🔗 {source['url']}"
           )
   
   # Додавання законодавства
   from src.rag.legislation import find_relevant_legislation
   legislation = find_relevant_legislation(query, [])  # Можна витягти з відповіді
   if legislation:
       result_parts.append("\n### ⚖️ Legislatívne základy")
       for leg in legislation:
           result_parts.append(
               f"- **{leg['law']}**  \n"
               f"  🔗 {leg['url']}  \n"
               f"  📑 Relevantné paragrafy: {', '.join(leg['sections'])}"
           )
   ```

4. **Візуалізація обґрунтування:**

   **Додати до відповіді візуальні індикатори:**
   ```python
   # Додати до системного промпту інструкцію про використання emoji
   # для позначення рівня впевненості:
   # ✅ - висока впевненість (знайдено в документах)
   # ⚠️ - середня впевненість (виведено з контексту)
   # ❓ - низька впевненість (потребує перевірки)
   ```

5. **Додавання "Reasoning Chain":**

   **Модифікувати промпт для включення ланцюжка міркувань:**
   ```python
   system_prompt += """
   
   REASONING CHAIN:
   Pre každé opatrenie uveď:
   1. Identifikovaná potreba žiaka
   2. Prečo toto opatrenie je vhodné
   3. Konkrétne kroky realizácie
   4. Očakávané výsledky
   """
   ```

---

### 5. Pridajte možnosť vlastných dokumentov

#### Поточний стан
- Система працює тільки з попередньо обробленими документами
- Немає можливості завантажити власні документи
- Відсутня інтеграція з документами про конкретного учня

#### Рекомендації щодо реалізації

1. **Архітектура рішення:**

   ```
   Завантаження документів (PDF, DOCX, TXT)
   ↓
   Обробка та конвертація в Markdown
   ↓
   Створення embeddings
   ↓
   Додавання до окремого індексу (student_documents)
   ↓
   Пошук в обох індексах (основному + студентському)
   ↓
   Об'єднання результатів
   ```

2. **Backend реалізація:**

   **Додати до `app.py`:**
   ```python
   from fastapi import UploadFile, File
   from typing import List
   import uuid
   from pathlib import Path
   
   UPLOAD_DIR = Path("data/uploads")
   UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
   
   @app.post("/api/upload-documents")
   async def upload_documents(
       files: List[UploadFile] = File(...),
       student_id: str = None
   ):
       """Завантаження документів про учня"""
       uploaded_files = []
       
       for file in files:
           # Генеруємо унікальне ім'я
           file_id = str(uuid.uuid4())
           file_ext = Path(file.filename).suffix
           file_path = UPLOAD_DIR / f"{file_id}{file_ext}"
           
           # Зберігаємо файл
           with open(file_path, "wb") as f:
               content = await file.read()
               f.write(content)
           
           # Обробляємо файл
           processed = await process_document(file_path, student_id)
           uploaded_files.append({
               "file_id": file_id,
               "filename": file.filename,
               "processed": processed
           })
       
       return {"files": uploaded_files}
   
   async def process_document(file_path: Path, student_id: str = None):
       """Обробка завантаженого документа"""
       from src.ingest import convert_to_markdown, create_student_index
       
       # Конвертація в Markdown
       md_content = convert_to_markdown(file_path)
       
       # Створення embeddings та додавання до індексу
       await create_student_index(md_content, student_id, file_path)
       
       return True
   ```

3. **Модуль обробки документів:**

   **Створити `src/rag/student_documents.py`:**
   ```python
   from pathlib import Path
   from langchain_huggingface import HuggingFaceEmbeddings
   from langchain_community.vectorstores import FAISS
   from langchain_text_splitters import RecursiveCharacterTextSplitter
   from langchain_core.documents import Document
   import json
   
   STUDENT_INDEX_DIR = Path("rag_index/student_documents")
   STUDENT_INDEX_DIR.mkdir(parents=True, exist_ok=True)
   
   def create_student_index(md_content: str, student_id: str, source_file: Path):
       """Створення індексу для документів учня"""
       # Розбиття на chunks
       splitter = RecursiveCharacterTextSplitter(
           chunk_size=1400,
           chunk_overlap=200
       )
       
       doc = Document(
           page_content=md_content,
           metadata={
               "student_id": student_id,
               "source_file": str(source_file),
               "type": "student_document"
           }
       )
       chunks = splitter.split_documents([doc])
       
       # Створення embeddings
       embedder = HuggingFaceEmbeddings(
           model_name=os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small"),
           encode_kwargs={"normalize_embeddings": True}
       )
       
       # Завантаження або створення індексу
       index_path = STUDENT_INDEX_DIR / f"{student_id}_index"
       
       if index_path.exists():
           # Додаємо до існуючого індексу
           vs = FAISS.load_local(
               str(index_path),
               embeddings=embedder,
               allow_dangerous_deserialization=True
           )
           vs.add_documents(chunks)
       else:
           # Створюємо новий індекс
           vs = FAISS.from_documents(chunks, embedder)
       
       vs.save_local(str(index_path))
   ```

4. **Інтеграція в пошук:**

   **Модифікувати `ask_cli.py`:**
   ```python
   def ask(query: str, student_id: str = None) -> str:
       vs = get_vectorstore()  # Основний індекс
       
       # Пошук в основному індексі
       docs_main = vs.similarity_search(query, k=15)
       
       # Пошук в студентських документах (якщо вказано)
       docs_student = []
       if student_id:
           from src.rag.student_documents import load_student_index
           student_vs = load_student_index(student_id)
           if student_vs:
               docs_student = student_vs.similarity_search(query, k=5)
               # Позначаємо як студентські документи
               for doc in docs_student:
                   doc.metadata["is_student_doc"] = True
       
       # Об'єднуємо результати (пріоритет студентським документам)
       docs_all = docs_student + docs_main
       
       # Продовжуємо з існуючою логікою...
   ```

5. **Frontend реалізація:**

   **Додати до `ui/index.html`:**
   ```html
   <div class="student-documents-section">
     <h3>📎 Документи про учня</h3>
     <div class="upload-area" id="upload-area">
       <input type="file" id="file-input" multiple accept=".pdf,.docx,.txt,.doc">
       <label for="file-input" class="upload-label">
         Перетягніть файли сюди або натисніть для вибору
       </label>
       <div id="uploaded-files"></div>
     </div>
     
     <div class="student-info">
       <label>
         ID учня (необов'язково):
         <input type="text" id="student-id" placeholder="Наприклад: student_001">
       </label>
     </div>
   </div>
   ```

   **Додати до `ui/js/main.js`:**
   ```javascript
   const fileInput = document.getElementById('file-input');
   const uploadedFilesDiv = document.getElementById('uploaded-files');
   
   fileInput.addEventListener('change', async (e) => {
       const files = Array.from(e.target.files);
       const studentId = document.getElementById('student-id').value;
       
       const formData = new FormData();
       files.forEach(file => formData.append('files', file));
       if (studentId) formData.append('student_id', studentId);
       
       try {
           const response = await fetch('/api/upload-documents', {
               method: 'POST',
               body: formData
           });
           
           const result = await response.json();
           uploadedFilesDiv.innerHTML = result.files.map(f => 
               `<div>✅ ${f.filename}</div>`
           ).join('');
       } catch (error) {
           console.error('Upload error:', error);
       }
   });
   
   // Модифікувати submitQuestion для включення student_id
   async function submitQuestion() {
       const studentId = document.getElementById('student-id').value;
       // ... існуючий код ...
       
       const response = await fetch('/api/ask', {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           body: JSON.stringify({ 
               question: q,
               student_id: studentId  // Додати student_id
           })
       });
   }
   ```

6. **Підтримка типів документів:**

   **Розширити `src/ingest/10_convert_docling.py` для підтримки DOCX:**
   ```python
   def convert_to_markdown(file_path: Path) -> str:
       if file_path.suffix == '.pdf' or file_path.suffix == '.html':
           # Використовуємо docling
           from docling.document_converter import DocumentConverter
           converter = DocumentConverter()
           doc = converter.convert(str(file_path))
           return doc.document_text
       
       elif file_path.suffix == '.docx':
           # Використовуємо python-docx
           from docx import Document
           doc = Document(str(file_path))
           return '\n'.join([para.text for para in doc.paragraphs])
       
       elif file_path.suffix == '.txt':
           return file_path.read_text(encoding='utf-8')
   ```

7. **Додати до `requirements.txt`:**
   ```python
   python-docx>=1.1.0  # для обробки DOCX
   python-multipart  # для завантаження файлів (вже є)
   ```

8. **Безпека та приватність:**
   - Шифрування студентських документів
   - Обмеження доступу до документів
   - Автоматичне видалення старих документів
   - Логування доступу

---

## 📊 Пріоритизація реалізації

### Високий пріоритет (рекомендовано реалізувати першими):
1. **Покращення пояснюваності результатів** (пункт 4)
   - Відносно просте в реалізації
   - Значно покращує UX
   - Не потребує додаткових залежностей

2. **Можливість власних документів** (пункт 5)
   - Критично важливо для практичного використання
   - Потребує більше роботи, але дає велику цінність

### Середній пріоритет:
3. **Зворотний зв'язок від педагога** (пункт 3)
   - Важливо для покращення системи
   - Потребує базу даних

4. **Перевірка результатів** (пункт 2)
   - Покращує якість відповідей
   - Може бути ресурсомістким

### Низький пріоритет (можна реалізувати пізніше):
5. **Пошук в інтернеті** (пункт 1)
   - Потребує додаткові API ключі
   - Може збільшити вартість експлуатації
   - Може знизити швидкість відповіді

---

## 🛠️ Технічні вимоги для реалізації

### Додаткові залежності:
```python
# requirements.txt додатки:
tavily-python>=0.3.0  # для веб-пошуку
python-docx>=1.1.0  # для обробки DOCX
```

### Додаткові API ключі:
- `TAVILY_API_KEY` (для веб-пошуку)
- Існуючі ключі (Anthropic/OpenAI) залишаються

### Інфраструктура:
- SQLite база даних для feedback
- Додатковий простір для зберігання студентських документів
- Розширення Dockerfile для підтримки нових залежностей

---

## 📝 Рекомендації щодо тестування

1. **Unit тести** для нових модулів
2. **Інтеграційні тести** для API endpoints
3. **E2E тести** для повного workflow
4. **Тести продуктивності** для веб-пошуку та обробки документів

---

## 🎯 Висновки

Всі п'ять вимог можуть бути реалізовані в рамках поточної архітектури проекту. Рекомендується почати з покращення пояснюваності та додавання можливості завантаження власних документів, оскільки вони дають найбільшу практичну цінність для користувачів.

---

**Дата створення:** 2026-01-27  
**Версія:** 1.0
