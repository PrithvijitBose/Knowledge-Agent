import html
import streamlit as st
import config
import github_auth
import knowledge_agent

# Page Configuration
st.set_page_config(
    page_title="Knowledge - GitHub Bot & AI Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark Glassmorphism Aesthetics in pure Python)
st.markdown("""
<style>
    /* Dark Theme Custom Palette */
    .main {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    }
    
    /* Header Styling */
    .app-title {
        font-family: 'Inter', sans-serif;
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #a855f7, #6366f1, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .app-subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Flow Diagram Cards */
    .flow-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    
    .flow-step {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #818cf8;
        font-weight: 700;
    }
    
    .flow-title {
        font-size: 1.2rem;
        color: #f8fafc;
        font-weight: 600;
        margin-top: 5px;
    }
    
    /* Badge styling */
    .status-badge-connected {
        background-color: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
    }
    
    .status-badge-disconnected {
        background-color: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
    }

    /* Comment Box */
    .comment-box {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 12px;
    }
    
    .comment-author {
        font-weight: bold;
        color: #a855f7;
        font-size: 0.95rem;
    }

    .knowledge-box {
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.4);
        border-radius: 10px;
        padding: 20px;
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "user_info" not in st.session_state:
        st.session_state.user_info = None
    if "repos" not in st.session_state:
        st.session_state.repos = []
    if "last_answer" not in st.session_state:
        st.session_state.last_answer = None


def handle_oauth_callback():
    """Detect OAuth callback query parameter 'code' and exchange for token."""
    query_params = st.query_params
    
    if "code" in query_params:
        code = query_params["code"]
        
        with st.spinner("Authorizing with GitHub..."):
            token = github_auth.exchange_code_for_token(code)
            if token:
                st.session_state.access_token = token
                user = github_auth.fetch_github_user(token)
                st.session_state.user_info = user
                st.session_state.repos = github_auth.fetch_user_repositories(token)
                
                # Clear code from URL query parameters after successful auth
                st.query_params.clear()
                st.toast("Successfully connected to GitHub!", icon="✅")
            else:
                st.error("Failed to authorize with GitHub. Please check your credentials and try again.")


def render_sidebar():
    """Render application sidebar with connection status and settings."""
    with st.sidebar:
        st.markdown("### ⚡ Knowledge Bot")
        st.markdown("---")
        
        if st.session_state.access_token and st.session_state.user_info:
            user = st.session_state.user_info
            st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                <img src="{user.get('avatar_url')}" style="border-radius: 50%; width: 80px; height: 80px; margin-bottom: 10px; border: 2px solid #818cf8;"/>
                <div style="font-weight: bold; color: #f8fafc; font-size: 1.1rem;">{user.get('name') or user.get('login')}</div>
                <div style="color: #94a3b8; font-size: 0.9rem;">@{user.get('login')}</div>
                <br/>
                <span class="status-badge-connected">Connected</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.metric(label="Total Repositories", value=len(st.session_state.repos))
            
            st.markdown("---")
            st.markdown("#### 🧠 AI Provider")
            all_providers = config.list_providers()
            provider_options = list(all_providers.keys())
            current_provider = st.session_state.get("selected_provider", "mistral")
            provider_idx = provider_options.index(current_provider) if current_provider in provider_options else 0
            selected_provider = st.selectbox(
                "Active LLM Engine",
                provider_options,
                index=provider_idx,
                format_func=lambda p: f"{p.capitalize()} {'(Configured)' if all_providers[p]['configured'] else '(Missing Key)'}"
            )
            st.session_state.selected_provider = selected_provider
            active_info = all_providers.get(selected_provider, {})
            st.caption(f"Model: `{active_info.get('model', 'default')}`")

            st.markdown("---")
            if st.button("🔌 Disconnect GitHub", use_container_width=True, type="secondary"):
                st.session_state.access_token = None
                st.session_state.user_info = None
                st.session_state.repos = []
                st.session_state.last_answer = None
                st.rerun()
        else:
            st.markdown("""
            <div style="text-align: center; padding: 10px;">
                <span class="status-badge-disconnected">Not Connected</span>
                <p style="color: #94a3b8; font-size: 0.9rem; margin-top: 15px;">Connect your GitHub account to choose and grant access to your repositories.</p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("#### 🧠 AI Provider")
            all_providers = config.list_providers()
            provider_options = list(all_providers.keys())
            current_provider = st.session_state.get("selected_provider", "mistral")
            provider_idx = provider_options.index(current_provider) if current_provider in provider_options else 0
            selected_provider = st.selectbox(
                "Active LLM Engine",
                provider_options,
                index=provider_idx,
                format_func=lambda p: f"{p.capitalize()} {'(Configured)' if all_providers[p]['configured'] else '(Missing Key)'}"
            )
            st.session_state.selected_provider = selected_provider
            active_info = all_providers.get(selected_provider, {})
            st.caption(f"Model: `{active_info.get('model', 'default')}`")

            st.markdown("---")
            st.info("💡 GitHub OAuth configured" if config.is_github_configured() else "⚠️ Requires .env OAuth keys")



def render_workflow_diagram():
    """Render the user perspective step-by-step workflow diagram."""
    st.markdown("#### 🔄 CodeRabbit-Style GitHub Workflow")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown("""
        <div class="flow-card">
            <div class="flow-step">Step 1</div>
            <div class="flow-title">Issue Created</div>
            <p style="font-size: 0.8rem; color: #94a3b8; margin-top: 5px;">Maintainer post</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="flow-card">
            <div class="flow-step">Step 2</div>
            <div class="flow-title">@Knowledge</div>
            <p style="font-size: 0.8rem; color: #94a3b8; margin-top: 5px;">Ask query in comment</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown("""
        <div class="flow-card">
            <div class="flow-step">Step 3</div>
            <div class="flow-title">Fetch Repo Docs</div>
            <p style="font-size: 0.8rem; color: #94a3b8; margin-top: 5px;">Reads GitHub files</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown("""
        <div class="flow-card">
            <div class="flow-step">Step 4</div>
            <div class="flow-title">Mistral AI</div>
            <p style="font-size: 0.8rem; color: #94a3b8; margin-top: 5px;">Summarizes answer</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col5:
        is_conn = bool(st.session_state.access_token)
        border_color = "rgba(34, 197, 94, 0.6)" if is_conn else "rgba(255, 255, 255, 0.1)"
        bg_color = "rgba(34, 197, 94, 0.15)" if is_conn else "rgba(30, 41, 59, 0.7)"
        st.markdown(f"""
        <div class="flow-card" style="border: 1px solid {border_color}; background: {bg_color};">
            <div class="flow-step">Step 5</div>
            <div class="flow-title">Post to GitHub</div>
            <p style="font-size: 0.8rem; color: {'#4ade80' if is_conn else '#94a3b8'}; margin-top: 5px;">
                {'💬 Reply on Issue' if is_conn else 'Pending auth'}
            </p>
        </div>
        """, unsafe_allow_html=True)
    st.write("")


def main():
    init_session_state()
    handle_oauth_callback()
    render_sidebar()
    
    # Title & Header
    st.markdown('<div class="app-title">Knowledge</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">Ask @Knowledge any question about a GitHub issue & repository — summarized by Mistral AI (mistral-small-2506) and posted back to GitHub</div>', unsafe_allow_html=True)
    
    # Render Workflow Visual
    render_workflow_diagram()
    
    st.markdown("---")
    
    # Check if credentials are set
    if not config.is_github_configured():
        st.warning("⚠️ **GitHub OAuth credentials not configured in `.env`**")
        st.markdown("""
        To test the live GitHub OAuth authorization flow, please update your `.env` file with your GitHub OAuth App keys:
        ```env
        GITHUB_CLIENT_ID=your_client_id
        GITHUB_CLIENT_SECRET=your_client_secret
        REDIRECT_URI=http://localhost:8501
        ```
        Refer to `README.md` for step-by-step guidance on creating a GitHub OAuth App.
        """)
    
    # Main View: Disconnected vs Connected
    if not st.session_state.access_token:
        st.subheader("Connect your GitHub Account")
        st.markdown("Grant **Knowledge** permission to access your repositories and sync data seamlessly.")
        
        auth_url = github_auth.get_authorization_url()
        
        st.write("")
        col_btn, col_empty = st.columns([1, 2])
        with col_btn:
            st.link_button(
                "🚀 Connect GitHub Account",
                auth_url,
                type="primary",
                use_container_width=True,
                disabled=not config.is_github_configured()
            )
            
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.4); padding: 20px; border-radius: 8px; margin-top: 25px; border-left: 4px solid #6366f1;">
            <h5 style="color: #f8fafc; margin-bottom: 8px;">🔒 What permissions are requested?</h5>
            <ul style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 0;">
                <li><b>read:user</b> — To display your profile and avatar in Knowledge</li>
                <li><b>repo</b> — To list repositories, read issues, read files, and post issue comments on GitHub</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    else:
        # Connected State - Show Tabs
        user = st.session_state.user_info or {}
        repos = st.session_state.repos or []
        
        st.success(f"🎉 **Connected as {user.get('login')}**")
        
        tab_hub, tab_repos, tab_profile, tab_token = st.tabs([
            "💬 @Knowledge Assistant (CodeRabbit Style)",
            "📦 Repositories", 
            "👤 Profile Details", 
            "🔑 Session Info"
        ])
        
        with tab_hub:
            st.markdown("### 💬 Ask @Knowledge Anything (CodeRabbit Style)")
            st.markdown("Pick a repository, select an Issue, ask `@Knowledge <any question>`, and post the response directly to GitHub.")
            
            if not repos:
                st.info("No repositories found for your account.")
            else:
                repo_options = {f"{r.get('full_name')}": r for r in repos}
                selected_repo_name = st.selectbox("📂 **Select Repository:**", list(repo_options.keys()))
                selected_repo = repo_options[selected_repo_name]
                
                owner = selected_repo.get("owner", {}).get("login")
                repo = selected_repo.get("name")
                
                with st.spinner(f"Fetching issues for {selected_repo_name}..."):
                    issues = github_auth.fetch_repo_issues(st.session_state.access_token, owner, repo)
                    
                # Simulation mode if no issues found
                if not issues:
                    st.warning(f"No open/closed issues found in `{selected_repo_name}`.")
                    st.markdown("#### 🧪 Interactive Simulation Mode (Issue #142 Example)")
                    demo_issue = {
                        "number": 142,
                        "title": "Modernize the authentication UI",
                        "body": "Modernize the authentication UI. Referencing closed PR #143 and merged PR #151 for structural details.",
                        "user": {"login": "Maintainer"}
                    }
                    demo_comments = [
                        {
                            "user": {"login": "Maintainer"},
                            "body": "Don't modify the OAuth flow."
                        },
                        {
                            "user": {"login": "Contributor"},
                            "body": "The UI is actually generated by AuthPanel."
                        },
                        {
                            "user": {"login": "Contributor"},
                            "body": "@Knowledge How should I start modernizing the authentication UI?"
                        }
                    ]
                    selected_issue = demo_issue
                    comments = demo_comments
                else:
                    issue_options = {f"#{i.get('number')}: {i.get('title')}": i for i in issues}
                    selected_issue_title = st.selectbox("📌 **Select Issue:**", list(issue_options.keys()))
                    selected_issue = issue_options[selected_issue_title]
                    
                    with st.spinner("Fetching comments thread..."):
                        comments = github_auth.fetch_issue_comments(
                            st.session_state.access_token, owner, repo, selected_issue.get("number")
                        )
                        
                # Display Selected Issue Details
                st.markdown("---")
                st.markdown(f"#### 📌 Issue #{selected_issue.get('number')}: {html.escape(str(selected_issue.get('title') or ''))}")
                st.caption(f"Posted by **@{html.escape(str(selected_issue.get('user', {}).get('login') or ''))}**")
                
                escaped_issue_body = html.escape(str(selected_issue.get('body') or '*No issue body content.*')).replace('\n', '<br>')
                st.markdown(f"""
                <div style="background: rgba(30, 41, 59, 0.5); border-left: 4px solid #818cf8; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                    {escaped_issue_body}
                </div>
                """, unsafe_allow_html=True)
                
                # Display Comments Thread
                st.markdown("##### 💬 Comments Thread")
                if not comments:
                    st.info("No comments on this issue yet.")
                    comments = [{
                        "user": {"login": "Contributor"},
                        "body": "@Knowledge What are the prerequisites?"
                    }]
                    
                for c in comments:
                    author = html.escape(str(c.get('user', {}).get('login') or ''))
                    body = html.escape(str(c.get('body') or '')).replace('\n', '<br>')
                    st.markdown(f"""
                    <div class="comment-box">
                        <div class="comment-author">@{author}</div>
                        <div style="color: #f8fafc; margin-top: 5px;">{body}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                st.write("")
                st.markdown("##### 🤖 Ask @Knowledge a Question")
                custom_q = st.text_input(
                    "Prompt @Knowledge (e.g. '@Knowledge How should I start?'):", 
                    value="@Knowledge How should I start modernizing the authentication UI?"
                )
                
                col_trig, col_blank = st.columns([1, 1])
                with col_trig:
                    trigger_btn = st.button("🚀 Generate Engineering Handoff (Context Expansion V1)", type="primary", use_container_width=True)
                    
                if trigger_btn:
                    prov = st.session_state.get("selected_provider", "mistral")
                    with st.spinner(f"🤖 Context Engine collecting PRs, comments & calling {prov.capitalize()} AI..."):
                        result = knowledge_agent.generate_knowledge_answer(
                            st.session_state.access_token,
                            owner,
                            repo,
                            selected_issue,
                            comments,
                            custom_query=custom_q,
                            provider_name=prov
                        )
                        st.session_state.last_answer = result
                        
                if st.session_state.last_answer:
                    result = st.session_state.last_answer
                    struct_ctx = result.get("structured_context", {})
                    
                    # Visual Context Engine Evidence Card
                    st.markdown("---")
                    st.markdown("#### 🧠 Context Engine Evidence Set")
                    col_pr, col_dir, col_files = st.columns(3)
                    
                    with col_pr:
                        st.markdown("**🔗 Linked PRs Found:**")
                        linked_prs = struct_ctx.get("linked_prs", [])
                        if not linked_prs:
                            st.caption("No linked PRs detected.")
                        else:
                            for pr in linked_prs:
                                badge = "🟢 Merged" if pr.get("merged") else "🔴 Closed"
                                st.markdown(f"- `{badge}` **PR #{pr['number']}**: {pr['title']}")
                                
                    with col_dir:
                        st.markdown("**🛡️ Maintainer Directives:**")
                        directives = struct_ctx.get("maintainer_directives", [])
                        if not directives:
                            st.caption("No explicit directives found.")
                        else:
                            for d in directives:
                                st.markdown(f"- **@{d['author']}**: *\"{d['body']}\"*")
                                
                    with col_files:
                        st.markdown("**📄 Referenced Files:**")
                        files = struct_ctx.get("fetched_files", {})
                        if not files:
                            st.caption("No files referenced.")
                        else:
                            for f in files.keys():
                                st.markdown(f"- `{f}`")

                    st.markdown("""
                    <div class="knowledge-box">
                        <h4 style="color: #818cf8; margin-bottom: 10px;">🤖 @Knowledge Engineering Handoff</h4>
                    """, unsafe_allow_html=True)
                    
                    st.caption(f"🧠 **Engine:** `{result['engine']}` | 📁 **Files Read:** `{', '.join(result['files_read']) or 'None'}`")
                    st.markdown(result["answer"])
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.write("")
                    col_post, col_view = st.columns([1, 1])
                    with col_post:
                        if st.button("💬 Post Answer Back to GitHub Issue", type="primary", use_container_width=True):
                            with st.spinner("Posting comment to GitHub issue..."):
                                success = github_auth.post_issue_comment(
                                    st.session_state.access_token,
                                    owner,
                                    repo,
                                    selected_issue.get("number"),
                                    result["answer"]
                                )
                                if success:
                                    st.toast("🎉 Successfully posted response to GitHub!", icon="✅")
                                    st.success("Comment posted to GitHub live thread!")
                                else:
                                    st.error("Failed to post comment to GitHub. Ensure OAuth token has 'repo' permissions.")
                                    
                    with col_view:
                        with st.expander("🔍 View Formatted Evidence Set Sent to LLM"):
                            st.code(struct_ctx.get("formatted_evidence", "*No evidence structured*"))


        with tab_repos:
            st.markdown(f"### Connected Repositories ({len(repos)})")
            
            # Repository search filter
            search_query = st.text_input("🔍 Search repositories...", "")
            filtered_repos = [
                r for r in repos 
                if search_query.lower() in r.get("name", "").lower() 
                or search_query.lower() in (r.get("description") or "").lower()
            ]
            
            if not filtered_repos:
                st.info("No matching repositories found.")
            else:
                for repo in filtered_repos:
                    with st.expander(f"📦 **{repo.get('full_name')}** {'🔒 Private' if repo.get('private') else '🌐 Public'}"):
                        col_r1, col_r2 = st.columns([3, 1])
                        with col_r1:
                            st.write(repo.get("description") or "No description provided.")
                            st.markdown(f"**Default Branch:** `{repo.get('default_branch')}` | **Language:** `{repo.get('language') or 'N/A'}`")
                        with col_r2:
                            st.link_button("View on GitHub ↗", repo.get("html_url"), use_container_width=True)
                            
        with tab_profile:
            st.markdown("### GitHub Profile Information")
            st.json(user)
            
        with tab_token:
            st.markdown("### Active OAuth Session")
            st.info("The access token is stored in Streamlit session state and can be passed to backend API calls.")
            st.code(f"Bearer {st.session_state.access_token[:10]}...[TRUNCATED]")


if __name__ == "__main__":
    main()
