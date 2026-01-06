
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

import database

def teach_growth():
    print("Force-feeding new capability to Rin...")
    
    success = database.add_to_core_kb(
        section="capabilities",
        key="self_evolution",
        data={
            "name": "Self Evolution",
            "description": "Rin can recursively improve her own knowledge base, memory, and logic parameters over time.",
            "status": "active",
            "source": "user_instruction",
            "version": "1.0"
        }
    )
    
    if success:
        print("Successfully added 'self_evolution' to Core KB.")
        print("Check logs/system_changes.log for proof!")
    else:
        print("Failed to update Core KB.")

if __name__ == "__main__":
    teach_growth()
