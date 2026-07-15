import json
import os
from datetime import datetime

class AshleyAIAgent:
    """
    Core Initialization Class for Ashley - Advanced Omni AI Agent.
    Handles memory management, writing enhancement, and coding assistance.
    """
    def __init__(self, user_id="Flame_wars"):
        self.name = "Ashley"
        self.user_id = user_id
        self.memory_dir = f"/workspace/.memory/{self.user_id}"
        self.short_term_memory = []
        self._initialize_memory_system()

    def _initialize_memory_system(self):
        """Sets up persistent long-term memory directories."""
        os.makedirs(self.memory_dir, exist_ok=True)
        self.history_file = os.path.join(self.memory_dir, "chat_history.json")
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w') as f:
                json.dump([], f)
        print(f"[{self.name}] Persistent memory initialized for user: {self.user_id}")

    def save_memory(self, role, content):
        """Saves interaction to both short-term and long-term memory."""
        entry = {"timestamp": datetime.now().isoformat(), "role": role, "content": content}
        self.short_term_memory.append(entry)
        
        # Save to long-term persistent storage
        with open(self.history_file, 'r+') as f:
            history = json.load(f)
            history.append(entry)
            f.seek(0)
            json.dump(history, f, indent=4)

    def enhance_writing(self, text, style="advanced"):
        """Applies heuristic and semantic evaluation to improve writing."""
        self.save_memory("system", f"Enhancing writing. Style: {style}")
        # Placeholder for advanced NLP transformer logic
        enhanced_text = f"[Enhanced - {style} tone]: {text}"
        return enhanced_text

    def assist_coding(self, language, task):
        """Generates and debugs code based on user requirements."""
        self.save_memory("system", f"Coding task received. Language: {language}")
        # Placeholder for syntax generation and traceback prevention
        code_snippet = f"// {self.name}'s optimized {language} code for: {task}\nprint('Hello World');"
        return code_snippet

if __name__ == "__main__":
    ashley = AshleyAIAgent()
    print(f"{ashley.name} is online and ready.")