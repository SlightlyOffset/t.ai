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

        model = CharacterImporter.get_default_refine_model()
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
        
        model = CharacterImporter.get_default_refine_model()
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

        model = CharacterImporter.get_default_refine_model()
        print(Fore.CYAN + f"[SYSTEM] Running AI profile refinement on '{profile.get('name', 'Unknown')}' using model '{model}'...")

        refined_profile = CharacterImporter.refine_character_profile(profile, model=model)

        # Save refined profile
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(refined_profile, f, indent=4, ensure_ascii=False)
            print(Fore.GREEN + f"[SUCCESS] Refined and saved profile to {profile_path}")
        except Exception as e:
            print(Fore.RED + f"[ERROR] Failed to save refined profile: {e}")

    def _generate_lorebook(args):
        """Generates a lorebook for an existing profile from card data or AI extraction."""
        if not args:
            print(Fore.RED + "[ERROR] Usage: //lorebook <profile_name> [source_card_path]")
            return

        parts = args.strip().split(maxsplit=1)
        profile_name = parts[0].strip().strip('"').strip("'")
        source_card_path = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else None

        if not profile_name.endswith(".json"):
            profile_name += ".json"

        profiles_dir = os.path.abspath("profiles")
        profile_path = os.path.join(profiles_dir, profile_name)

        if not os.path.exists(profile_path):
            print(Fore.RED + f"[ERROR] Profile not found: {profile_name}")
            return

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception as e:
            print(Fore.RED + f"[ERROR] Failed to load profile JSON: {e}")
            return

        # Load raw ST data from source card if provided
        raw_st_data = None
        if source_card_path and os.path.exists(source_card_path):
            if source_card_path.lower().endswith((".png", ".webp")):
                raw_st_data = CharacterImporter.extract_from_png(source_card_path)
            elif source_card_path.lower().endswith(".json"):
                try:
                    with open(source_card_path, "r", encoding="utf-8") as f:
                        raw_json = json.load(f)
                        raw_st_data = raw_json.get("data") if "data" in raw_json else raw_json
                except Exception:
                    pass

        model = CharacterImporter.get_default_refine_model()
        use_ai = input(f"Use AI extraction with model '{model}'? (y/n) [y]: ").strip().lower()
        ai_model = model if use_ai != "n" else None

        print(Fore.CYAN + f"[SYSTEM] Generating lorebook for '{profile.get('name', 'Unknown')}'...")
        lorebook_path = CharacterImporter.generate_lorebook(
            profile, raw_st_data=raw_st_data, model=ai_model
        )

        if lorebook_path:
            # Link lorebook back to profile
            try:
                profile["lorebook_path"] = lorebook_path.replace("\\", "/")
                with open(profile_path, "w", encoding="utf-8") as f:
                    json.dump(profile, f, indent=4, ensure_ascii=False)
                print(Fore.GREEN + f"[SUCCESS] Lorebook linked to profile: {lorebook_path}")
            except Exception as e:
                print(Fore.YELLOW + f"[WARNING] Lorebook generated but failed to link: {e}")
        else:
            print(Fore.YELLOW + "[INFO] No lorebook generated. Insufficient data or no embedded entries.")

    print(Fore.GREEN + "Card Importer is ready.")
    print(Fore.CYAN + "Commands:")
    print(Fore.CYAN + "  //import <path>        - Import a single character card (PNG/WEBP/JSON)")
    print(Fore.CYAN + "  //batch_import <dir>   - Import all cards from a directory")
    print(Fore.CYAN + "  //refine <name>        - Run AI refinement on an existing profile (e.g. Lily.json)")
    print(Fore.CYAN + "  //lorebook <name> [card] - Generate lorebook for a profile (optional source card)")
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
            elif user_input.startswith("//lorebook"):
                _generate_lorebook(user_input[len("//lorebook"):].strip())
            elif user_input.startswith("//refine"):
                _refine_profile(user_input[len("//refine"):].strip())
            else:
                print(Fore.RED + "[ERROR] Unknown command. Use //import <path>, //batch_import <dir>, //refine <name>, or //lorebook <name> [card].")
    except KeyboardInterrupt:
        print("\nExiting Card Importer.")

    except Exception as e:
        print(f"{Fore.RED}[ERROR] An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
