"""Memory - persistent storage for conversations and knowledge"""
import json
import time
from pathlib import Path


class Memory:
    """
    Persistent memory - stores conversations and facts.
    Like hard drive in a computer.
    """

    def __init__(self):
        self.base_dir = Path.home() / ".lazarus" / "memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_file = self.base_dir / "conversations.json"
        self.facts_file = self.base_dir / "facts.json"

    def _load_conversations(self):
        if self.conversations_file.exists():
            return json.loads(self.conversations_file.read_text("utf-8"))
        return []

    def _save_conversations(self, data):
        self.conversations_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), "utf-8"
        )

    def _load_facts(self):
        if self.facts_file.exists():
            return json.loads(self.facts_file.read_text("utf-8"))
        return {}

    def _save_facts(self, data):
        self.facts_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), "utf-8"
        )

    def save_message(self, role, content):
        """Save a message to conversation history"""
        conversations = self._load_conversations()
        conversations.append({
            "role": role,
            "content": content,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        # Keep last 100 messages
        conversations = conversations[-100:]
        self._save_conversations(conversations)

    def get_history(self, limit=20):
        """Get recent conversation history"""
        conversations = self._load_conversations()
        return [{"role": m["role"], "content": m["content"]}
                for m in conversations[-limit:]]

    def save_fact(self, key, value):
        """Save a fact (like user preferences)"""
        facts = self._load_facts()
        facts[key] = {"value": value, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        self._save_facts(facts)

    def get_fact(self, key):
        """Get a saved fact"""
        facts = self._load_facts()
        if key in facts:
            return facts[key]["value"]
        return None

    def get_all_facts(self):
        """Get all saved facts"""
        facts = self._load_facts()
        return {k: v["value"] for k, v in facts.items()}

    def clear(self):
        """Clear all memory"""
        self._save_conversations([])
        self._save_facts({})
