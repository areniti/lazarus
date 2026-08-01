"""Config Management - like CPU control registers"""
import json
import secrets
from pathlib import Path


class Config:
    """Central configuration - stored in ~/.lazarus/config.json"""

    def __init__(self):
        self.base_dir = Path.home() / ".lazarus"
        self.config_file = self.base_dir / "config.json"
        self.output_dir = self.base_dir / "output"
        self.data = self._load()

    def _load(self):
        if self.config_file.exists():
            return json.loads(self.config_file.read_text("utf-8"))
        return {
            "username": "admin",
            "password": self._gen_password(),
            "domain": "",
            "api": {"url": "", "key": "", "model": "mimo-v2.5-free"},
            "is_first_run": True,
        }

    def save(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8")

    def setup_wizard(self):
        """First-run wizard"""
        print("🔧 LAZARUS Setup Wizard")
        print("=" * 40)

        # Username
        u = input(f"Username [{self.data['username']}]: ").strip()
        if u:
            self.data["username"] = u

        # Password
        print(f"Generated password: {self.data['password']}")
        p = input("New password (Enter to keep): ").strip()
        if p:
            self.data["password"] = p

        # API
        print("\n🌐 API Configuration")
        url = input("API URL [https://opencode.ai/zen/v1/chat/completions]: ").strip()
        if url:
            self.data["api"]["url"] = url
        else:
            self.data["api"]["url"] = "https://opencode.ai/zen/v1/chat/completions"

        key = input("API Key: ").strip()
        if key:
            self.data["api"]["key"] = key

        model = input(f"Model [{self.data['api']['model']}]: ").strip()
        if model:
            self.data["api"]["model"] = model

        self.data["is_first_run"] = False
        self.save()
        print("\n✅ Config saved!")

    def is_configured(self):
        return (
            self.data.get("api", {}).get("key")
            and self.data.get("api", {}).get("url")
            and not self.data.get("is_first_run")
        )

    def login(self, username, password):
        return (username == self.data["username"] and password == self.data["password"])

    @staticmethod
    def _gen_password():
        return secrets.token_urlsafe(12)
