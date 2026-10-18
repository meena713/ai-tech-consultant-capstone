import os,json,sqlite3,uuid
from contextlib import closing
from typing import Any
import httpx
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
DB_PATH=os.getenv("TASK3_DB_PATH","/data/proposals.db")
KNOWLEDGE_URL=os.getenv("KNOWLEDGE_URL","http://localhost:8000")
MODEL=os.getenv("ANTHROPIC_MODEL","claude-sonnet-4-5")
app=FastAPI(title="Task 3 — Meeting to SOW")
def db():
 os.makedirs(os.path.dirname(DB_PATH) or ".",exist_ok=True)
 c=sqlite3.connect(DB_PATH);c.row_factory=sqlite3.Row;return c
@app.on_event("startup")
def startup():
 with closing(db()) as c:
  c.execute("""CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,transcript TEXT NOT NULL,
  proposal_json TEXT NOT NULL,approved INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP)""");c.commit()
class Generate(BaseModel): transcript:str=Field(min_length=30,max_length=50000)
class FollowUp(BaseModel): transcript:str=Field(min_length=10,max_length=50000)
class Approval(BaseModel):
 approved:bool
 reviewer:str=Field(min_length=1,max_length=200)
 notes:str=Field(default="",max_length=5000)
def ask_knowledge(q:str)->dict[str,Any]:
 try:
  r=httpx.post(f"{KNOWLEDGE_URL}/ask",json={"question":q},timeout=35);r.raise_for_status();return r.json()
 except Exception as e:raise HTTPException(502,f"Knowledge API failed: {str(e)[:160]}")

def generate_json(system: str, user: str) -> dict[str, Any]:
    """Create a basic structured response without calling a paid AI API."""
    if "TRANSCRIPT:" in user:
        transcript = user.split("TRANSCRIPT:", 1)[1].split(
            "\nKNOWLEDGE:", 1
        )[0].strip()

        return {
            "summary": (
                "Demo statement of work based on the supplied meeting transcript. "
                "Review all details with the client before approval."
            ),
            "assumptions": [
                "The transcript may not contain every project requirement.",
                "Budget, delivery date, and final technical details need confirmation.",
                "Hours are illustrative estimates, not a binding quote."
            ],
            "scope_items": [
                {
                    "title": "Requirements and project discovery",
                    "type": "discovery",
                    "hours": 4,
                    "rationale": "Confirm requirements, priorities, and unresolved questions."
                },
                {
                    "title": "Website design and responsive layout",
                    "type": "custom",
                    "hours": 12,
                    "rationale": "Estimate for designing desktop and mobile page layouts."
                },
                {
                    "title": "Membership registration and login",
                    "type": "custom",
                    "hours": 12,
                    "rationale": "Estimate for implementing member account workflows."
                },
                {
                    "title": "Business directory, search, and filtering",
                    "type": "custom",
                    "hours": 12,
                    "rationale": "Estimate for directory listings and finding businesses."
                },
                {
                    "title": "Membership plans and contact form",
                    "type": "custom",
                    "hours": 8,
                    "rationale": "Estimate for membership plan pages and contact submission."
                },
                {
                    "title": "Admin dashboard",
                    "type": "custom",
                    "hours": 12,
                    "rationale": "Estimate for managing members and business listings."
                },
                {
                    "title": "Testing and handover",
                    "type": "custom",
                    "hours": 8,
                    "rationale": "Estimate for basic testing, fixes, and handover."
                }
            ],
            "questions": [
                "What is the approved project budget?",
                "What is the required delivery date?",
                "Which payment provider, if any, should membership plans use?",
                "Who can access the admin dashboard?",
                "Who will provide the content, branding, and business listings?"
            ],
            "out_of_scope": [
                "Third-party payment integration until requirements are confirmed.",
                "Ongoing hosting, maintenance, and support unless agreed separately."
            ],
            "risks": [
                "Requirements may change after discovery.",
                "Integrations and security requirements may affect the estimate.",
                "The timeline cannot be confirmed until dependencies are known."
            ],
            "estimated_total_hours": 68,
            "evidence_sources": [
                "Meeting transcript supplied by the user",
                "Free demo template; estimates and features require human validation"
            ],
            "demo_mode": True
        }

    if "FOLLOW-UP:" in user:
        return {
            "changes": [
                {
                    "item": "Scope comparison",
                    "classification": "needs_clarification",
                    "explanation": (
                        "Free demo mode does not perform an AI comparison. "
                        "A human must compare the previous proposal with the follow-up."
                    )
                }
            ],
            "updated_questions": [
                "Which exact scope items should be added, changed, or removed?"
            ],
            "updated_risks": [
                "Changes have not been automatically analyzed or validated."
            ],
            "demo_mode": True
        }

    return {
        "summary": "Free demo response; manual review is required.",
        "assumptions": ["Requirements need human validation."],
        "scope_items": [],
        "questions": ["What specific requirements should be included?"],
        "out_of_scope": [],
        "risks": ["This response was not generated by an AI model."],
        "estimated_total_hours": 0,
        "evidence_sources": ["Free demo mode"],
        "demo_mode": True
    }
@app.get("/health")
def health():return {"status":"ok","service":"meeting-to-sow"}

@app.post("/generate")
def generate(req: Generate):
    evidence = ask_knowledge(
        "Identify relevant documented native product capabilities. "
        "Separate verified facts from unknowns.\n" + req.transcript
    )

    system = (
        "Draft a careful Statement of Work. "
        "Use the supplied transcript and evidence cautiously. "
        "Do not invent verified product capabilities."
    )

    proposal = generate_json(
        system,
        "TRANSCRIPT:\n" + req.transcript
        + "\nKNOWLEDGE:\n" + json.dumps(evidence, ensure_ascii=False)
    )

    pid = str(uuid.uuid4())
    proposal.update({
        "proposal_id": pid,
        "status": "pending_approval",
        "approved": False
    })

    with closing(db()) as c:
        c.execute(
            "INSERT INTO proposals(id,transcript,proposal_json) VALUES(?,?,?)",
            (pid, req.transcript, json.dumps(proposal))
        )
        c.commit()

    return proposal
@app.get("/proposals/{proposal_id}")
def get_proposal(proposal_id:str):
 with closing(db()) as c:row=c.execute("SELECT * FROM proposals WHERE id=?",(proposal_id,)).fetchone()
 if row is None:raise HTTPException(404,"Proposal not found")
 return {"proposal":json.loads(row["proposal_json"]),"approved":bool(row["approved"]),"created_at":row["created_at"]}
@app.post("/proposals/{proposal_id}/follow-up")
def follow_up(proposal_id:str,req:FollowUp):
 with closing(db()) as c:row=c.execute("SELECT * FROM proposals WHERE id=?",(proposal_id,)).fetchone()
 if row is None:raise HTTPException(404,"Proposal not found")
 previous=json.loads(row["proposal_json"])
 evidence=ask_knowledge("Check documented native product capabilities relevant to these changes:\n"+req.transcript)
 comparison=generate_json("""Compare previous scope with follow-up transcript. Return JSON keys changes, updated_questions, updated_risks.
Each changes entry has item, classification, explanation. classification must be unchanged, changed, added, removed,
out_of_scope, or needs_clarification. Do not silently add work to approved scope.""",
"PREVIOUS:\n"+json.dumps(previous,ensure_ascii=False)+"\nFOLLOW-UP:\n"+req.transcript+"\nKNOWLEDGE:\n"+json.dumps(evidence,ensure_ascii=False))
 return {"proposal_id":proposal_id,"current_status":"pending_human_review","comparison":comparison,
 "note":"Review the comparison and explicitly approve a revised scope before committing changes."}
@app.post("/proposals/{proposal_id}/approve")
def approve(proposal_id:str,req:Approval):
 with closing(db()) as c:
  row=c.execute("SELECT proposal_json FROM proposals WHERE id=?",(proposal_id,)).fetchone()
  if row is None:raise HTTPException(404,"Proposal not found")
  p=json.loads(row["proposal_json"]);p.update({"approved":req.approved,"status":"approved" if req.approved else "rejected",
  "reviewer":req.reviewer,"review_notes":req.notes})
  c.execute("UPDATE proposals SET proposal_json=?,approved=? WHERE id=?",(json.dumps(p),int(req.approved),proposal_id));c.commit()
 return {"proposal_id":proposal_id,"status":p["status"],"approved":req.approved,"reviewer":req.reviewer}
