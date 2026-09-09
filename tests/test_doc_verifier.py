import unittest
from knowledge_agent.doc_verifier import (
    DocClaimExtractor,
    CodeSymbolExtractor,
    DocDiscrepancyDetector,
    DiscrepancyType,
    format_discrepancy_report,
)


class TestDocVerifier(unittest.TestCase):
    def test_doc_claim_extractor_http_endpoints(self):
        markdown = """
# API Documentation
Use `POST /api/v1/auth/login` to authenticate.
You can also fetch user profile via `GET /api/v1/users/{id}`.
        """
        claims = DocClaimExtractor.extract_claims("README.md", markdown)
        endpoints = [c for c in claims if c["type"] == "HTTP_ENDPOINT"]
        self.assertEqual(len(endpoints), 2)
        self.assertEqual(endpoints[0]["method"], "POST")
        self.assertEqual(endpoints[0]["endpoint"], "/api/v1/auth/login")
        self.assertEqual(endpoints[1]["method"], "GET")
        self.assertEqual(endpoints[1]["endpoint"], "/api/v1/users/{id}")

    def test_doc_claim_extractor_functions_and_args(self):
        markdown = """
### Helpers
Call `verify_token(token, secret, algorithm="HS256")` before proceeding.
Use `create_session(user_id)` to initialize user state.
        """
        claims = DocClaimExtractor.extract_claims("docs/auth.md", markdown)
        funcs = [c for c in claims if c["type"] == "FUNCTION"]
        self.assertEqual(len(funcs), 2)
        self.assertEqual(funcs[0]["symbol"], "verify_token")
        self.assertEqual(funcs[0]["args"], ["token", "secret", "algorithm"])
        self.assertEqual(funcs[1]["symbol"], "create_session")
        self.assertEqual(funcs[1]["args"], ["user_id"])

    def test_doc_claim_extractor_env_vars(self):
        markdown = """
Set `DATABASE_URL` in `.env` and configure `MISTRAL_API_KEY`.
Do not forget `PORT` or common words like `README`.
        """
        claims = DocClaimExtractor.extract_claims("README.md", markdown)
        env_vars = [c["symbol"] for c in claims if c["type"] == "ENV_VAR"]
        self.assertIn("DATABASE_URL", env_vars)
        self.assertIn("MISTRAL_API_KEY", env_vars)
        self.assertNotIn("README", env_vars)  # Stopword filtered

    def test_code_symbol_extractor_python_ast(self):
        py_code = """
import os

__all__ = ["AuthService", "login"]

class AuthService:
    def validate_password(self, password):
        return True

def login(user, pass_hash):
    db_uri = os.getenv("POSTGRES_URI")
    secret = os.environ["APP_SECRET"]
    return True
        """
        symbols = CodeSymbolExtractor.extract_symbols("auth.py", py_code)
        self.assertIn("login", symbols["functions"])
        self.assertEqual(symbols["functions"]["login"]["args"], ["user", "pass_hash"])
        self.assertIn("AuthService", symbols["classes"])
        self.assertIn("validate_password", symbols["classes"]["AuthService"]["methods"])
        self.assertIn("POSTGRES_URI", symbols["env_vars"])
        self.assertIn("APP_SECRET", symbols["env_vars"])
        self.assertIn("AuthService", symbols["all_exports"])

    def test_code_symbol_extractor_route_decorators(self):
        py_code = """
from fastapi import FastAPI

app = FastAPI()

@app.post("/api/v1/auth/login")
def login():
    return {"token": "123"}

@app.get("/api/v1/users/{id}")
async def get_user(id: int):
    return {"id": id}
        """
        symbols = CodeSymbolExtractor.extract_symbols("api.py", py_code)
        routes = symbols["routes"]
        self.assertEqual(len(routes), 2)
        self.assertEqual(routes[0]["method"], "POST")
        self.assertEqual(routes[0]["path"], "/api/v1/auth/login")
        self.assertEqual(routes[1]["method"], "GET")
        self.assertEqual(routes[1]["path"], "/api/v1/users/{id}")

    def test_code_symbol_extractor_syntax_error_resilience(self):
        # File has invalid syntax (e.g. truncated snippet)
        invalid_code = "def broken_func(:\n   return invalid"
        symbols = CodeSymbolExtractor.extract_symbols("broken.py", invalid_code)
        self.assertIsInstance(symbols["functions"], dict)

    def test_discrepancy_detector_finds_missing_implementation(self):
        docs = {
            "README.md": """
# Features
Uses `OAuthManager` to handle login.
Call `verify_jwt_token(token)` to check signature.
Endpoint: `POST /api/v1/oauth/callback`
            """
        }
        code_files = {
            "main.py": """
def simple_login(username, password):
    return True
            """
        }
        res = DocDiscrepancyDetector.detect_discrepancies(docs, code_files)
        discrepancies = res["discrepancies"]
        types = [d["type"] for d in discrepancies]
        claims = [d["claim"] for d in discrepancies]

        self.assertIn(DiscrepancyType.MISSING_IMPLEMENTATION, types)
        self.assertTrue(any("verify_jwt_token" in c for c in claims))
        self.assertTrue(any("OAuthManager" in c for c in claims))
        self.assertTrue(any("POST /api/v1/oauth/callback" in c for c in claims))

    def test_discrepancy_detector_finds_signature_mismatch(self):
        docs = {
            "README.md": """
Call `authenticate(user_id, session_token)` to login.
            """
        }
        code_files = {
            "auth.py": """
def authenticate(username, password, remember_me=False):
    return True
            """
        }
        res = DocDiscrepancyDetector.detect_discrepancies(docs, code_files)
        mismatches = [d for d in res["discrepancies"] if d["type"] == DiscrepancyType.SIGNATURE_MISMATCH]
        self.assertEqual(len(mismatches), 1)
        self.assertIn("authenticate", mismatches[0]["claim"])
        self.assertIn("auth.py", mismatches[0]["source_file"])

    def test_discrepancy_detector_finds_missing_env_var(self):
        docs = {
            "README.md": """
Configure `DATABASE_URL` in your environment.
            """
        }
        code_files = {
            "config.py": """
import os
DB_HOST = os.getenv("DB_HOST", "localhost")
            """
        }
        res = DocDiscrepancyDetector.detect_discrepancies(docs, code_files)
        env_discrepancies = [d for d in res["discrepancies"] if d["type"] == DiscrepancyType.MISSING_ENV_VAR]
        self.assertEqual(len(env_discrepancies), 1)
        self.assertEqual(env_discrepancies[0]["claim"], "DATABASE_URL")

    def test_discrepancy_detector_clean_when_aligned(self):
        docs = {
            "README.md": """
Set `MISTRAL_API_KEY` in `.env`.
Call `generate_answer(query)` to answer questions.
Endpoint: `GET /api/v1/health`
            """
        }
        code_files = {
            "agent.py": """
import os
from fastapi import FastAPI
app = FastAPI()

api_key = os.getenv("MISTRAL_API_KEY")

def generate_answer(query):
    return "answer"

@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
            """
        }
        res = DocDiscrepancyDetector.detect_discrepancies(docs, code_files)
        self.assertEqual(res["total_discrepancies"], 0)
        report = format_discrepancy_report(res["discrepancies"])
        self.assertIn("✅", report)


if __name__ == "__main__":
    unittest.main()
