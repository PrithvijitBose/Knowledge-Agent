import os
import hmac
import hashlib
import json
import config
import bot

try:
    from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
    import uvicorn
except ImportError:
    FastAPI = None
    Request = None
    BackgroundTasks = None
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)
    uvicorn = None

if FastAPI is not None:
    app = FastAPI(
        title="Knowledge GitHub Webhook Server",
        description="Listens for native GitHub @Knowledge comment webhooks and replies automatically."
    )
else:
    app = None

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload_bytes: bytes, signature_header: str | None) -> bool:
    """Verify HMAC-SHA256 signature from GitHub webhook header."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET") or GITHUB_WEBHOOK_SECRET
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_mac = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    expected_header = f"sha256={expected_mac}"
    return hmac.compare_digest(expected_header, signature_header)


if app is not None:
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
        body_bytes = await request.body()
        signature_header = request.headers.get("X-Hub-Signature-256")

        # Verify webhook signature if secret is configured
        if os.getenv("GITHUB_WEBHOOK_SECRET") or GITHUB_WEBHOOK_SECRET:
            if not verify_signature(body_bytes, signature_header):
                raise HTTPException(status_code=401, detail="Invalid webhook signature (X-Hub-Signature-256 mismatch)")

        event_type = request.headers.get("X-GitHub-Event")

        # We listen for issue_comment events
        if event_type != "issue_comment":
            return {"status": "ignored", "reason": f"Event type '{event_type}' not handled"}

        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

        action = payload.get("action")
        if action != "created":
            return {"status": "ignored", "reason": f"Action '{action}' not handled"}

        sender = payload.get("sender", {})
        comment = payload.get("comment", {})
        comment_user = comment.get("user", {})
        if sender.get("type") == "Bot" or comment_user.get("type") == "Bot":
            return {"status": "ignored", "reason": "Comment created by a Bot account"}

        body = comment.get("body", "")
        author = comment_user.get("login", "")

        # Check if @Knowledge is mentioned in the comment
        if "@Knowledge" not in body and "@knowledge" not in body:
            return {"status": "ignored", "reason": "No @Knowledge tag in comment body"}

        issue = payload.get("issue", {})
        issue_number = issue.get("number")

        repository = payload.get("repository", {})
        owner = repository.get("owner", {}).get("login")
        repo = repository.get("name")

        # Get access token from env
        token = os.getenv("GITHUB_TOKEN")

        if not token or not owner or not repo or not issue_number:
            raise HTTPException(status_code=500, detail="Missing repository context or GITHUB_TOKEN environment variable")

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
            "message": f"Triggered Knowledge bot for {owner}/{repo} Issue #{issue_number}"
        }


if __name__ == "__main__":
    if uvicorn is not None and app is not None:
        print("🚀 Starting Knowledge GitHub Webhook Server on http://0.0.0.0:8000...")
        uvicorn.run("webhook_server:app", host="0.0.0.0", port=8000, reload=True)
    else:
        print("Error: fastapi and uvicorn are required to run webhook_server.py directly.")
