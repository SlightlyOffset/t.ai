import os
import json

from colorama import Fore

from engines.character_importer import import_character, CharacterImporter


def main():
    """Simple script to import cards from a file or directory."""
    def _import_card(args):
        """Imports a character card (PNG, WEBP or JSON) from SillyTavern format."""
        if not args:
            print(Fore.RED + "[ERROR] Usage: //import <path_to_card_png_or_json>")
            return

        path = args.strip().strip('"').strip("'")
        if not os.path.exists(path):
            print(Fore.RED + f"[ERROR] File not found: {path}")
            return

        from engines.config import get_setting
        model = get_setting("importer_model") or get_setting("default_llm_model", "llama3.2")
        refine_choice = input(f"Would you like to run AI refinement using local model '{model}'? (y/n) [n]: ").strip().lower()
        refine = refine_choice in ["y", "yes"]

        import_character(path, refine=refine)

    def _batch_import(args):
        """Imports all character cards from a directory."""
        if not args:
            print(Fore.RED + "[ERROR] Usage: //batch_import <directory_path>")
            return

        dir_path = args.strip().strip('"').strip("'")
        if not os.path.isdir(dir_path):
            print(Fore.RED + f"[ERROR] Directory not found: {dir_path}")
            return

        files = [f for f in os.listdir(dir_path) if f.lower().endswith((".png", ".webp", ".json"))]
        if not files:
            print(Fore.YELLOW + f"[INFO] No valid character files found in {dir_path}")
            return

        print(Fore.CYAN + f"[SYSTEM] Found {len(files)} potential cards. Starting batch import...")
        
        from engines.config import get_setting
        model = get_setting("importer_model") or get_setting("default_llm_model", "llama3.2")
        refine_choice = input(f"Would you like to run AI refinement on ALL imported cards using '{model}'? (y/n) [n]: ").strip().lower()
        refine = refine_choice in ["y", "yes"]

        success_count = 0
        for f in files:
            full_path = os.path.join(dir_path, f)
            print(Fore.WHITE + f" -> Importing {f}...")
            if import_character(full_path, refine=refine):
                success_count += 1
        
        print(Fore.GREEN + f"\n[SUCCESS] Batch import complete. {success_count}/{len(files)} characters imported.")

    def _refine_profile(args):
        """Runs AI refinement on an already existing profile file."""
        if not args:
            print(Fore.RED + "[ERROR] Usage: //refine <profile_name_or_file>")
            return

        profile_name = args.strip().strip('"').strip("'")
        if not profile_name.endswith(".json"):
            profile_name += ".json"

        profiles_dir = os.path.abspath("profiles")
        profile_path = os.path.join(profiles_dir, profile_name)

        if not os.path.exists(profile_path):
            # Try to see if it matches a path directly
            profile_path = os.path.abspath(profile_name)
            if not os.path.exists(profile_path):
                print(Fore.RED + f"[ERROR] Profile not found: {profile_name}")
                return

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception as e:
            print(Fore.RED + f"[ERROR] Failed to load profile JSON: {e}")
            return

        from engines.config import get_setting
        model = get_setting("importer_model") or get_setting("default_llm_model", "llama3.2")
        print(Fore.CYAN + f"[SYSTEM] Running AI profile refinement on '{profile.get('name', 'Unknown')}' using model '{model}'...")

        refined_profile = CharacterImporter.refine_character_profile(profile, model=model)

        # Save refined profile
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(refined_profile, f, indent=4, ensure_ascii=False)
            print(Fore.GREEN + f"[SUCCESS] Refined and saved profile to {profile_path}")
        except Exception as e:
            print(Fore.RED + f"[ERROR] Failed to save refined profile: {e}")

    print(Fore.GREEN + "Card Importer is ready.")
    print(Fore.CYAN + "Commands:")
    print(Fore.CYAN + "  //import <path>        - Import a single character card (PNG/WEBP/JSON)")
    print(Fore.CYAN + "  //batch_import <dir>   - Import all cards from a directory")
    print(Fore.CYAN + "  //refine <name>        - Run AI refinement on an existing profile (e.g. Lily.json)")
    print(Fore.CYAN + "  Ctrl+C                 - Exit")

    try:
        while True:
            user_input = input("\nEnter command: ").strip()
            if not user_input:
                continue

            if user_input.startswith("//batch_import"):
                _batch_import(user_input[len("//batch_import"):].strip())
            elif user_input.startswith("//import"):
                _import_card(user_input[len("//import"):].strip())
            elif user_input.startswith("//refine"):
                _refine_profile(user_input[len("//refine"):].strip())
            else:
                print(Fore.RED + "[ERROR] Unknown command. Use //import <path>, //batch_import <dir> or //refine <name>.")
    except KeyboardInterrupt:
        print("\nExiting Card Importer.")

    except Exception as e:
        print(f"{Fore.RED}[ERROR] An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
