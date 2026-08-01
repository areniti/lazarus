"""Config Management"""
import json
import secrets
from pathlib import Path


# Available models for selection
MODELS = [
    "mimo-v2.5-free",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-5-sonnet",
    "claude-3-haiku",
    "deepseek-chat",
    "deepseek-coder",
    "gemini-pro",
]

# Known API providers
PROVIDERS = [
    ("OpenCode Zen", "https://opencode.ai/zen/v1/chat/completions"),
    ("OpenAI", "https://api.openai.com/v1/chat/completions"),
    ("Anthropic", "https://api.anthropic.com/v1/chat/completions"),
    ("DeepSeek", "https://api.deepseek.com/v1/chat/completions"),
    ("Custom", ""),
]


class Config:
    """Central configuration"""

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
        self.config_file.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8"
        )

    def setup_wizard(self):
        """First-run wizard with model list"""
        print()
        print("╔═══════════════════════════════════════╗")
        print("║   🔧 L A Z A R U S - Setup Wizard    ║")
        print("╚═══════════════════════════════════════╝")
        print()

        # Username
        u = input(f"👤 Username [{self.data['username']}]: ").strip()
        if u:
            self.data["username"] = u

        # Password
        print(f"🔑 Generated password: {self.data['password']}")
        p = input("   New password (Enter to keep): ").strip()
        if p:
            self.data["password"] = p

        print()
        print("🌐 API Configuration")
        print("-" * 40)

        # Show providers
        print("Select API provider:")
        for i, (name, url) in enumerate(PROVIDERS):
            print(f"  {i+1}. {name}")
        choice = input(f"Choice [1]: ").strip()
        try:
            idx = int(choice) - 1
            provider_name, provider_url = PROVIDERS[idx]
        except (ValueError, IndexError):
            provider_name, provider_url = PROVIDERS[0]

        if provider_url:
            self.data["api"]["url"] = provider_url
            print(f"  → {provider_url}")
        else:
            url = input("   Custom API URL: ").strip()
            if url:
                # Auto-append /chat/completions if missing
                if not url.endswith("/chat/completions"):
                    if url.endswith("/"):
                        url += "chat/completions"
                    else:
                        url += "/chat/completions"
                self.data["api"]["url"] = url

        # API Key
        key = input("🔑 API Key: ").strip()
        if key:
            self.data["api"]["key"] = key

        # Model selection
        print()
        print("📋 Available models:")
        for i, model in enumerate(MODELS):
            print(f"  {i+1}. {model}")
        model_choice = input(f"Choice [1]: ").strip()
        try:
            model_idx = int(model_choice) - 1
            self.data["api"]["model"] = MODELS[model_idx]
        except (ValueError, IndexError):
            self.data["api"]["model"] = MODELS[0]
        print(f"  → {self.data['api']['model']}")

        self.data["is_first_run"] = False
        self.save()
        print()
        print("✅ Config saved!")

    def is_configured(self):
        return not self.data.get("is_first_run", True)

    def login(self, username, password):
        return username == self.data["username"] and password == self.data["password"]

    @staticmethod
    def _gen_password():
        return secrets.token_urlsafe(12)
