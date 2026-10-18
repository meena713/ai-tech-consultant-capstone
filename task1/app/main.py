import os, re, time, sqlite3, hashlib, xml.etree.ElementTree as ET
from contextlib import closing
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

SITEMAP = "https://support.brilliantdirectories.com/support/sitemap.xml"
HOST = urlparse(SITEMAP).hostname
DB_PATH = os.getenv("TASK1_DB_PATH", "/data/knowledge.db")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
app = FastAPI(title="Task 1 — Knowledge Brain")

def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
    return c

def init_db():
    with closing(db()) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS articles(url TEXT PRIMARY KEY,title TEXT NOT NULL,
          content TEXT NOT NULL,content_hash TEXT NOT NULL,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS expert_tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,
          question TEXT NOT NULL,answer TEXT,status TEXT DEFAULT 'open',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """); c.commit()

@app.on_event("startup")
def startup(): init_db()

def get_urls():
    with httpx.Client(timeout=25, follow_redirects=True) as client:
        r = client.get(SITEMAP); r.raise_for_status()
    root = ET.fromstring(r.text); urls = []
    for node in root.iter():
        if node.tag.endswith("loc") and node.text:
            u = node.text.strip(); p = urlparse(u)
            if p.scheme == "https" and p.hostname == HOST: urls.append(u)
    if not urls: raise ValueError("No permitted URLs in sitemap")
    return list(dict.fromkeys(urls))

def parse_article(url):
    p = urlparse(url)
    if p.scheme != "https" or p.hostname != HOST: raise ValueError("Unapproved host")
    with httpx.Client(timeout=25, follow_redirects=True) as client:
        r = client.get(url); r.raise_for_status()
        final = urlparse(str(r.url))
        if final.scheme != "https" or final.hostname != HOST: raise ValueError("Redirect host not permitted")
    soup = BeautifulSoup(r.text, "html.parser")
    for e in soup(["script","style","nav","footer","header","noscript"]): e.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    main = soup.find("main") or soup.find("article") or soup.body or soup
    content = re.sub(r"\s+", " ", main.get_text(" ", strip=True)).strip()[:40000]
    if len(content) < 30: raise ValueError("Not enough readable text")
    return title[:500], content, hashlib.sha256(content.encode()).hexdigest()

@app.get("/health")
def health():
    with closing(db()) as c: count = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    return {"status":"ok","service":"knowledge-brain","indexed_articles":count}

@app.post("/sync")
def sync():
    try: urls = get_urls()
    except Exception as e: raise HTTPException(502, f"Sitemap fetch failed: {str(e)[:180]}")
    processed, failed = 0, []
    with closing(db()) as c:
        for i, url in enumerate(urls):
            try:
                title, content, digest = parse_article(url)
                c.execute("""INSERT INTO articles(url,title,content,content_hash) VALUES(?,?,?,?)
                ON CONFLICT(url) DO UPDATE SET title=excluded.title,content=excluded.content,
                content_hash=excluded.content_hash,updated_at=CURRENT_TIMESTAMP
                WHERE articles.content_hash != excluded.content_hash""",
                (url,title,content,digest)); c.commit(); processed += 1
            except Exception as e: failed.append({"url":url,"error":str(e)[:160]})
            if i < len(urls)-1: time.sleep(0.5)
    # Never purge existing records after a partial crawl.
    return {"urls_found":len(urls),"processed":processed,"failed_count":len(failed),"failures":failed[:25]}

def retrieve(question, limit=5):
    terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", question) if len(t)>2]
    if not terms: return []
    with closing(db()) as c: rows = c.execute("SELECT url,title,content FROM articles").fetchall()
    scored = []
    for row in rows:
        haystack = (row["title"]+" "+row["content"]).lower()
        score = sum(haystack.count(t) for t in set(terms))
        if score: scored.append((score,dict(row)))
    scored.sort(key=lambda x:x[0], reverse=True)
    return [r for _,r in scored[:limit]]

def new_expert_task(question):
    with closing(db()) as c:
        cur = c.execute("INSERT INTO expert_tasks(question) VALUES(?)",(question,)); c.commit()
        return cur.lastrowid

class Ask(BaseModel):
    question: str = Field(min_length=3,max_length=2000)

@app.post("/ask")
def ask(req: Ask):
    articles = retrieve(req.question)
    if not articles:
        return {"answer":"I could not find supporting documentation. Please ask a human expert.",
                "sources":[],"needs_human":True,"expert_task_id":new_expert_task(req.question)}
    sources = [{"title":a["title"],"url":a["url"]} for a in articles]
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"answer":"Model API is not configured. These matching articles need human review.",
                "sources":sources,"evidence":[a["content"][:1000] for a in articles],
                "needs_human":True,"expert_task_id":new_expert_task(req.question)}
    
    
    context = "\n\n".join(
        f"Title: {a['title']}\nSource: {a['url']}\nContent: {a['content'][:1500]}"
        for a in articles
    )

    answer = (
        "Free demonstration mode (no paid AI API configured).\n\n"
        f"Your question: {req.question}\n\n"
        "Here is the relevant information retrieved from the support knowledge base:\n\n"
        f"{context[:5000]}\n\n"
        "Please open the source links below to verify the full instructions. "
        "This response presents retrieved article content; it is not an AI-generated summary."
    )

    task = new_expert_task(req.question)
    return {
        "answer": answer,
        "sources": sources,
        "evidence": [a["content"][:1000] for a in articles],
        "needs_human": True,
        "expert_task_id": task
    }


@app.get("/expert-tasks")
def expert_tasks():
    with closing(db()) as c: rows = c.execute("SELECT * FROM expert_tasks ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]

class ExpertAnswer(BaseModel):
    answer: str = Field(min_length=1,max_length=10000)

@app.post("/expert-tasks/{task_id}/answer")
def answer_expert(task_id:int, req:ExpertAnswer):
    with closing(db()) as c:
        cur = c.execute("UPDATE expert_tasks SET answer=?,status='answered' WHERE id=?",(req.answer,task_id)); c.commit()
    if not cur.rowcount: raise HTTPException(404,"Expert task not found")
    return {"id":task_id,"status":"answered"}
