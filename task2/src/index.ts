import express from "express";
import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import fs from "node:fs";
import path from "node:path";

const app=express(); app.use(express.json({limit:"1mb"}));
const PORT=Number(process.env.PORT||3000);
const KNOWLEDGE_URL=process.env.KNOWLEDGE_URL||"http://localhost:8000";
const MODEL=process.env.ANTHROPIC_MODEL||"claude-sonnet-4-5";
const DATA_PATH=process.env.INBOX_DATA_PATH||path.join(process.cwd(),"data","feedback.json");
type Category="how_to"|"refund"|"complaint"|"quote"|"follow_up"|"other";
type Feedback={category:Category;unchanged:boolean;createdAt:string};
type Store={feedback:Feedback[];streaks:Partial<Record<Category,number>>};
function load():Store{try{return JSON.parse(fs.readFileSync(DATA_PATH,"utf8")) as Store}catch{return {feedback:[],streaks:{}}}}
let store=load();
function save(){fs.mkdirSync(path.dirname(DATA_PATH),{recursive:true});fs.writeFileSync(DATA_PATH,JSON.stringify(store,null,2))}
function classify(subject:string,body:string):Category{
 const t=`${subject} ${body}`.toLowerCase();
 if(/refund|chargeback|money back|cancel my payment/.test(t))return "refund";
 if(/complaint|unacceptable|angry|terrible service/.test(t))return "complaint";
 if(/price|pricing|quote|estimate|how much/.test(t))return "quote";
 if(/following up|follow-up|checking in|any update/.test(t))return "follow_up";
 if(/how do i|how can i|steps|where can i|how to/.test(t))return "how_to";
 return "other";
}
function normalize(t:string){return t.trim().replace(/\r\n/g,"\n").replace(/[ \t]+/g," ")}
async function askKnowledge(question:string):Promise<any>{
 const r=await fetch(`${KNOWLEDGE_URL}/ask`,{method:"POST",headers:{"Content-Type":"application/json"},
 body:JSON.stringify({question}),signal:AbortSignal.timeout(30000)});
 if(!r.ok)throw new Error(`Knowledge API returned ${r.status}`);return r.json();
}
const Email=z.object({emailId:z.string().min(1),subject:z.string().max(500).default(""),body:z.string().min(3).max(20000)});
const FeedbackSchema=z.object({category:z.enum(["how_to","refund","complaint","quote","follow_up","other"]),originalDraft:z.string().min(1),finalReply:z.string().min(1)});
const sensitive=new Set<Category>(["refund","complaint"]);
app.get("/health",(_req,res)=>res.json({status:"ok",service:"inbox-agent"}));
app.post("/draft",async(req,res)=>{
 const p=Email.safeParse(req.body);if(!p.success)return res.status(400).json({error:p.error.flatten()});
 const e=p.data,category=classify(e.subject,e.body);let k:any;
 try{k=await askKnowledge(`Help answer this customer email.\nSubject: ${e.subject}\nBody: ${e.body}`)}
 catch{return res.status(502).json({error:"Knowledge service unavailable; no draft generated."})}
 
let draft: string;

draft =
  `Hello,\n\n` +
  `Thank you for contacting us about: ${e.subject || e.body}\n\n` +
  `Here is information from our support knowledge base:\n\n` +
  `${k.answer || "We will need to review the relevant support documentation to answer your question."}\n\n` +
  `Please review the source links provided and contact our support team if you need further assistance.\n\n` +
  `Best regards,\nSupport Team`;
  const streak=store.streaks[category]||0;

 return res.json({emailId:e.emailId,category,draft,sources:k.sources||[],requiresHumanReview:sensitive.has(category)||k.needs_human===true,
 unchangedDraftsInARow:streak,automationEligible:streak>=20,sentAutomatically:false});
});
app.post("/feedback",(req,res)=>{
 const p=FeedbackSchema.safeParse(req.body);if(!p.success)return res.status(400).json({error:p.error.flatten()});
 const {category,originalDraft,finalReply}=p.data,unchanged=normalize(originalDraft)===normalize(finalReply);
 store.streaks[category]=unchanged?(store.streaks[category]||0)+1:0;
 store.feedback.push({category,unchanged,createdAt:new Date().toISOString()});save();
 return res.json({category,unchanged,unchangedDraftsInARow:store.streaks[category],automationEligible:(store.streaks[category]||0)>=20,
 note:"Eligibility only; automatic sending is intentionally not implemented."});
});
app.get("/automation",(_req,res)=>{
 const categories:Category[]=["how_to","refund","complaint","quote","follow_up","other"];
 res.json({categories:categories.map(category=>({category,unchangedDraftsInARow:store.streaks[category]||0,
 eligibleForReview:(store.streaks[category]||0)>=20,autoSendEnabled:false})),feedbackCount:store.feedback.length});
});
if(require.main===module)app.listen(PORT,()=>console.log(`Inbox Agent listening on ${PORT}`));
export {classify,normalize,app};
