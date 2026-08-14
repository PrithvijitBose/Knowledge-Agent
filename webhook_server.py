import os
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
import uvicorn
import config
import bot

app = FastAPI(
    title="Knowledge GitHub Webhook Server",
    description="Listens for native GitHub @Knowledge comment webhooks and replies automatically."
)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "app": "Knowledge GitHub Bot",
        "mistral_model": config.MISTRAL_MODEL,
        "mistral_active": config.is_mistral_configured()
    }


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    GitHub Webhook listener endpoint (event: issue_comment).
    When someone posts '@Knowledge <question>' on GitHub, GitHub pings this endpoint.
    """
    event_type = request.headers.get("X-GitHub-Event")
    
    # We listen for issue_comment events
    if event_type != "issue_comment":
        return {"status": "ignored", "reason": f"Event type '{event_type}' not handled"}
        
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")
        
    action = payload.get("action")
    if action != "created":
        return {"status": "ignored", "reason": f"Action '{action}' not handled"}
        
    comment = payload.get("comment", {})
    body = comment.get("body", "")
    author = comment.get("user", {}).get("login", "")
    
    # Check if @Knowledge or /knowledge is mentioned in the comment
    body_lower = body.lower()
    if "@knowledge" not in body_lower and "/knowledge" not in body_lower:
        return {"status": "ignored", "reason": "No @Knowledge or /knowledge trigger in comment body"}
        
    issue = payload.get("issue", {})
    issue_number = issue.get("number")
    
    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login")
    repo = repository.get("name")
    
    # Get access token from env or installation token
    token = os.getenv("GITHUB_TOKEN") or config.GITHUB_CLIENT_SECRET
    
    if not token or not owner or not repo or not issue_number:
        raise HTTPException(status_code=500, detail="Missing repository context or GitHub token")
        
    print(f"📥 Received Webhook from GitHub: @{author} mentioned @Knowledge on {owner}/{repo} Issue #{issue_number}")
    
    # Process headlessly in background task
    background_tasks.add_task(
        bot.process_github_comment,
        access_token=token,
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        comment_body=body,
        comment_author=author
    )
    
    return {
        "status": "processing",
        "message": f"Triggered @Knowledge bot for {owner}/{repo} Issue #{issue_number}"
    }


if __name__ == "__main__":
    print("🚀 Starting Knowledge GitHub Webhook Server on http://0.0.0.0:8000...")
    uvicorn.run("webhook_server:app", host="0.0.0.0", port=8000, reload=True)
