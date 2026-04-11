import os
import json
from engines.responses import generate_summary
from engines.memory_v2 import memory_manager
from engines.config import get_setting

def create_long_history(profile_name):
    history = []
    for i in range(20):
        history.append({"role": "user", "content": f"User message {i}: Tell me a story about a cat."})
        history.append({"role": "assistant", "content": f"Assistant message {i}: Once upon a time, there was a cat named Whiskers who loved {i} mice."})
    
    memory_manager.save_history(profile_name, history)
    print(f"Created long history for {profile_name} with {len(history)} messages.")

def verify():
    profile_name = "test_summarizer"
    create_long_history(profile_name)
    
    history_data = memory_manager.get_full_data(profile_name)
    history = history_data.get("history", [])
    
    if len(history) > 15:
        older = history[:-5]
        recent = history[-5:]
        print(f"Summarizing {len(older)} messages...")
        
        # Default to gemma2:2b
        model = get_setting("summarizer_model", "gemma2:2b")
        
        print(f"Using model: {model}")
        summary = generate_summary(older, model=model)
        
        print("\n--- GENERATED SUMMARY ---")
        print(summary)
        print("--------------------------\n")
        
        print(f"Recent history starts with: {recent[0]['content']}")
    else:
        print("History not long enough to test.")

if __name__ == "__main__":
    verify()
