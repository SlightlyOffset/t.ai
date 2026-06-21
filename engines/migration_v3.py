"""
Auto-Migration Manager for character profile directories.
Migrates legacy flat profiles, avatars, lorebooks, and history files
into consolidated, self-contained character subdirectories atomically on startup.
"""

import os
import shutil
import sys
import json
from engines.utilities import sanitize_profile_name, save_json_atomic
from engines.config import get_setting, update_setting

def safe_print(*args, sep=" ", end="\n"):
    msg = sep.join(str(arg) for arg in args)
    try:
        sys.stdout.write(msg + end)
        sys.stdout.flush()
    except (UnicodeEncodeError, IOError):
        encoding = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
        try:
            sys.stdout.buffer.write(msg.encode(encoding, errors='replace') + end.encode(encoding, errors='replace'))
            sys.stdout.flush()
        except Exception:
            try:
                sys.stdout.write(msg.encode('ascii', errors='replace').decode('ascii') + end)
                sys.stdout.flush()
            except Exception:
                pass

# Override print for this module to avoid Windows console UnicodeEncodeError
print = safe_print


class MigrationManager:
    @staticmethod
    def run_migration() -> None:
        """
        Scans 'profiles/' for legacy flat JSON files and migrates them 
        into unified self-contained subdirectories atomically.
        """
        profiles_dir = "profiles"
        if not os.path.exists(profiles_dir):
            return

        # Scan for legacy character JSON profiles in profiles/
        # (Must be files directly under profiles/, excluding directories)
        legacy_files = []
        try:
            for entry in os.scandir(profiles_dir):
                if entry.is_file() and entry.name.endswith(".json") and entry.name != "settings.json":
                    try:
                        with open(entry.path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, dict) and "name" in data:
                                legacy_files.append((entry.name, entry.path, data))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[MIGRATION] [ERROR] Failed to scan profiles folder: {e}")
            return

        if not legacy_files:
            return

        print(f"[MIGRATION] Found {len(legacy_files)} legacy character profiles to migrate.")

        for filename, old_path, profile in legacy_files:
            char_name = profile.get("name", "").strip()
            if not char_name:
                continue

            safe_char = sanitize_profile_name(char_name)
            # Use original filename stem (without hash or .json) as the folder name 
            # to match sanitize_profile_name or card_hash
            folder_name = os.path.splitext(filename)[0]
            char_dir = os.path.join(profiles_dir, folder_name)
            os.makedirs(char_dir, exist_ok=True)

            print(f"[MIGRATION] Migrating '{char_name}' to self-contained folder '{char_dir}'...")

            # 1. Migrate sessions
            sessions_dir = os.path.join(char_dir, "sessions")
            os.makedirs(sessions_dir, exist_ok=True)
            
            # Move flat sessions in history/
            old_history_dir = os.path.join("history", folder_name)
            if os.path.isdir(old_history_dir):
                for hist_file in os.listdir(old_history_dir):
                    old_h_path = os.path.join(old_history_dir, hist_file)
                    new_h_path = os.path.join(sessions_dir, hist_file)
                    try:
                        shutil.move(old_h_path, new_h_path)
                    except Exception as e:
                        print(f"[MIGRATION] [ERROR] Failed to move session file {hist_file}: {e}")
                try:
                    shutil.rmtree(old_history_dir)
                except Exception:
                    pass
            
            # Move flat character_history.json
            old_flat_history = os.path.join("history", f"{folder_name}_history.json")
            if os.path.exists(old_flat_history):
                try:
                    shutil.move(old_flat_history, os.path.join(sessions_dir, "default_history.json"))
                except Exception as e:
                    print(f"[MIGRATION] [ERROR] Failed to move flat history file: {e}")
            old_flat_history_bak = old_flat_history + ".bak"
            if os.path.exists(old_flat_history_bak):
                try:
                    shutil.move(old_flat_history_bak, os.path.join(sessions_dir, "default_history.json.bak"))
                except Exception:
                    pass

            # 2. Migrate avatar
            avatar_path = profile.get("avatar_path")
            if avatar_path:
                if os.path.exists(avatar_path) and os.path.isfile(avatar_path):
                    ext = os.path.splitext(avatar_path)[1]
                    new_avatar_filename = f"avatar{ext}"
                    new_avatar_path = os.path.join(char_dir, new_avatar_filename)
                    try:
                        shutil.copy2(avatar_path, new_avatar_path)
                        profile["avatar_path"] = new_avatar_filename
                        print(f"[MIGRATION] Moved avatar '{avatar_path}' to '{new_avatar_path}'")
                    except Exception as e:
                        print(f"[MIGRATION] [WARNING] Failed to copy avatar image: {e}")
                else:
                    # Check if avatar image file exists in img/ folder with matching character name
                    found_avatar = False
                    if os.path.exists("img"):
                        for entry in os.scandir("img"):
                            if entry.is_file() and (entry.name.startswith(folder_name) or entry.name.startswith(safe_char)):
                                ext = os.path.splitext(entry.name)[1]
                                new_avatar_filename = f"avatar{ext}"
                                new_avatar_path = os.path.join(char_dir, new_avatar_filename)
                                try:
                                    shutil.copy2(entry.path, new_avatar_path)
                                    profile["avatar_path"] = new_avatar_filename
                                    print(f"[MIGRATION] Found and moved matching avatar '{entry.path}' to '{new_avatar_path}'")
                                    found_avatar = True
                                    break
                                except Exception:
                                    pass
                    if not found_avatar:
                        profile["avatar_path"] = "img/No_Image_Error.png"
            else:
                profile["avatar_path"] = "img/No_Image_Error.png"

            # 3. Migrate lorebook
            lore_path = profile.get("lorebook_path")
            if lore_path:
                if os.path.exists(lore_path) and os.path.isfile(lore_path):
                    new_lore_path = os.path.join(char_dir, "lorebook.json")
                    try:
                        shutil.copy2(lore_path, new_lore_path)
                        profile["lorebook_path"] = "lorebook.json"
                        print(f"[MIGRATION] Moved lorebook '{lore_path}' to '{new_lore_path}'")
                    except Exception as e:
                        print(f"[MIGRATION] [WARNING] Failed to copy lorebook: {e}")
                else:
                    # Look in lorebooks/ folder for [folder_name].json or [safe_char].json
                    found_lore = False
                    for possible_lore in (f"lorebooks/{folder_name}.json", f"lorebooks/{safe_char}.json"):
                        if os.path.exists(possible_lore):
                            new_lore_path = os.path.join(char_dir, "lorebook.json")
                            try:
                                shutil.copy2(possible_lore, new_lore_path)
                                profile["lorebook_path"] = "lorebook.json"
                                print(f"[MIGRATION] Found and moved matching lorebook '{possible_lore}' to '{new_lore_path}'")
                                found_lore = True
                                break
                            except Exception:
                                pass
                    if not found_lore:
                        profile["lorebook_path"] = ""
            else:
                profile["lorebook_path"] = ""

            # 4. Save updated profile JSON to profile.json inside char_dir
            new_profile_path = os.path.join(char_dir, "profile.json")
            try:
                save_json_atomic(new_profile_path, profile)
                print(f"[MIGRATION] Saved updated profile config to '{new_profile_path}'")
            except Exception as e:
                try:
                    with open(new_profile_path, "w", encoding="utf-8") as f:
                        json.dump(profile, f, indent=4, ensure_ascii=False)
                except Exception as ex:
                    print(f"[MIGRATION] [CRITICAL] Failed to write profile: {ex}")
                    continue

            # 5. Clean up old flat JSON profile file
            try:
                os.remove(old_path)
                print(f"[MIGRATION] Cleaned up legacy profile file '{old_path}'")
            except Exception as e:
                print(f"[MIGRATION] [WARNING] Failed to remove old profile file: {e}")

            # 6. Update current active profile in settings.json if it matched
            curr_active = get_setting("current_character_profile")
            if curr_active == filename:
                new_rel_setting = f"{folder_name}/profile.json"
                update_setting("current_character_profile", new_rel_setting)
                print(f"[MIGRATION] Updated active character setting to '{new_rel_setting}'")

        print("[MIGRATION] Character directory migration completed successfully.")
