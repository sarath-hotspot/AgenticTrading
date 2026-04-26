import base64
import hashlib
import time
import requests


class QuantConnectError(Exception):
    pass


PROJECT_FOLDER = "AIAgent_007"


class QuantConnectClient:
    BASE_URL = "https://www.quantconnect.com/api/v2"
    COMPILE_POLL_INTERVAL = 3   # seconds
    COMPILE_TIMEOUT = 120       # seconds
    BACKTEST_POLL_INTERVAL = 10 # seconds
    BACKTEST_TIMEOUT = 600      # seconds

    def __init__(self, user_id: str, api_token: str):
        self.user_id = user_id
        self.api_token = api_token

    def _auth_headers(self) -> dict:
        """Build SHA-256 timestamp-based auth headers. Recomputed each call."""
        ts = str(int(time.time()))
        hash_bytes = hashlib.sha256(f"{self.api_token}:{ts}".encode()).hexdigest()
        credentials = base64.b64encode(f"{self.user_id}:{hash_bytes}".encode()).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Timestamp": ts,
        }

    def _request(self, endpoint: str, data: dict | None = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = requests.post(
            url,
            headers=self._auth_headers(),
            json=data or {},
            timeout=90,
        )
        try:
            result = response.json()
        except Exception:
            raise QuantConnectError(f"Non-JSON response ({response.status_code}): {response.text[:200]}")
        if not result.get("success", True):
            errors = result.get("errors", [result])
            raise QuantConnectError(f"QC API error on {endpoint} (HTTP {response.status_code}): {errors}")
        return result

    def authenticate(self) -> bool:
        result = self._request("/authenticate")
        return result.get("success", False)

    def create_project(self, name: str) -> int:
        # Always place projects inside the AIAgent_007 folder
        if not name.startswith(f"{PROJECT_FOLDER}/"):
            name = f"{PROJECT_FOLDER}/{name}"
        result = self._request("/projects/create", {"name": name, "language": "Py"})
        return result["projects"][0]["projectId"]

    def create_file(self, project_id: int, name: str, content: str) -> None:
        self._request("/files/create", {"projectId": project_id, "name": name, "content": content})

    def update_file(self, project_id: int, name: str, content: str) -> None:
        self._request("/files/update", {"projectId": project_id, "name": name, "content": content})

    def compile(self, project_id: int) -> str:
        result = self._request("/compile/create", {"projectId": project_id})
        return result["compileId"]

    def get_compile_status(self, project_id: int, compile_id: str) -> dict:
        return self._request("/compile/read", {"projectId": project_id, "compileId": compile_id})

    def wait_for_compile(self, project_id: int, compile_id: str) -> dict:
        deadline = time.time() + self.COMPILE_TIMEOUT
        while time.time() < deadline:
            status = self.get_compile_status(project_id, compile_id)
            state = status.get("state", "")
            if state == "BuildSuccess":
                return {"success": True, "state": state}
            if state == "BuildError":
                logs = status.get("logs", [])
                return {"success": False, "state": state, "logs": logs}
            time.sleep(self.COMPILE_POLL_INTERVAL)
        raise QuantConnectError(f"Compile timed out after {self.COMPILE_TIMEOUT}s")

    def run_backtest(self, project_id: int, compile_id: str, backtest_name: str) -> str:
        result = self._request("/backtests/create", {
            "projectId": project_id,
            "compileId": compile_id,
            "backtestName": backtest_name,
        })
        return result["backtest"]["backtestId"]

    def get_backtest_status(self, project_id: int, backtest_id: str) -> dict:
        result = self._request("/backtests/read", {"projectId": project_id, "backtestId": backtest_id})
        return result["backtest"]

    def wait_for_backtest(self, project_id: int, backtest_id: str) -> dict:
        deadline = time.time() + self.BACKTEST_TIMEOUT
        while time.time() < deadline:
            backtest = self.get_backtest_status(project_id, backtest_id)
            if backtest.get("completed"):
                return backtest
            time.sleep(self.BACKTEST_POLL_INTERVAL)
        raise QuantConnectError(f"Backtest timed out after {self.BACKTEST_TIMEOUT}s")

    def read_backtest_logs(self, project_id: int, backtest_id: str, start: int = 0, count: int = 500) -> list[str]:
        """Fetch algorithm log output from a completed backtest."""
        try:
            result = self._request("/backtests/read/log", {
                "projectId": project_id,
                "backtestId": backtest_id,
                "start": start,
                "end": start + count,
            })
            return result.get("logs", [])
        except QuantConnectError:
            return []


# --- Anthropic tool definitions ---

TOOL_QC_CREATE_PROJECT = {
    "name": "qc_create_project",
    "description": "Create a new QuantConnect project. Returns the project_id.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Project name"},
        },
        "required": ["name"],
    },
}

TOOL_QC_UPLOAD_CODE = {
    "name": "qc_upload_code",
    "description": (
        "Upload or replace the main.py algorithm code in a QuantConnect project. "
        "Use this after qc_create_project and after each compile error to fix code."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer", "description": "Project ID from qc_create_project"},
            "algorithm_code": {"type": "string", "description": "Full Python source code"},
            "is_update": {
                "type": "boolean",
                "description": "True if replacing existing file, False for first upload",
            },
        },
        "required": ["project_id", "algorithm_code"],
    },
}

TOOL_QC_COMPILE_AND_RUN = {
    "name": "qc_compile_and_run",
    "description": (
        "Compile the project and run a backtest. "
        "Returns compile errors (if any) or the backtest_id on success."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer"},
            "backtest_name": {"type": "string", "description": "Name for this backtest run"},
        },
        "required": ["project_id", "backtest_name"],
    },
}

TOOL_QC_READ_RESULTS = {
    "name": "qc_read_results",
    "description": "Poll and return the completed backtest results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer"},
            "backtest_id": {"type": "string"},
        },
        "required": ["project_id", "backtest_id"],
    },
}
