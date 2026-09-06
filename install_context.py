# install_context.py
import sys
import os
import winreg

def get_forge_exe_path():
    if getattr(sys, 'frozen', False):
        return sys.executable
    else:
        exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Forge.exe')
        if os.path.exists(exe_path):
            return exe_path
        return input("Enter full path to Forge.exe: ")

def register_context_menu():
    forge_path = get_forge_exe_path()
    if not os.path.exists(forge_path):
        print(f"Error: Forge.exe not found at {forge_path}")
        return

    commands = {
        "compress_zip": {
            "verb": "Compress to ZIP",
            "cmd": f'"{forge_path}" compress -o "%1.zip" -i %* --algo deflate'
        },
        "compress_xz": {
            "verb": "Compress to XZ",
            "cmd": f'"{forge_path}" compress -o "%1.tar.xz" -i %* --algo lzma'
        },
        "compress_zst": {
            "verb": "Compress to ZST",
            "cmd": f'"{forge_path}" compress -o "%1.tar.zst" -i %* --algo zstd'
        },
        "extract": {
            "verb": "Extract with Forge",
            "cmd": f'"{forge_path}" extract "%1" -o "%1_extracted"'
        }
    }

    root_keys = [
        (winreg.HKEY_CLASSES_ROOT, r"*\shell\Forge"),
        (winreg.HKEY_CLASSES_ROOT, r"Folder\shell\Forge"),
    ]

    for hkey, key_path in root_keys:
        key = winreg.CreateKey(hkey, key_path)
        winreg.SetValue(key, None, winreg.REG_SZ, "Forge")
        winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, "Forge")
        winreg.SetValueEx(key, "SubCommands", 0, winreg.REG_SZ, ";".join(commands.keys()))
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, forge_path)
        winreg.CloseKey(key)

    for cmd_name, cmd_info in commands.items():
        for hkey, root_path in root_keys:
            sub_key_path = f"{root_path}\\shell\\{cmd_name}"
            sub_key = winreg.CreateKey(hkey, sub_key_path)
            winreg.SetValue(sub_key, None, winreg.REG_SZ, cmd_info["verb"])
            command_key = winreg.CreateKey(sub_key, "command")
            winreg.SetValue(command_key, None, winreg.REG_SZ, cmd_info["cmd"])
            winreg.CloseKey(command_key)
            winreg.CloseKey(sub_key)

    print("Explorer context menu installed successfully!")
    print("You can now right-click files/folders and use Forge.")

def unregister_context_menu():
    keys_to_remove = [
        r"*\shell\Forge",
        r"Folder\shell\Forge",
    ]
    for key_path in keys_to_remove:
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, key_path)
            print(f"Removed {key_path}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error removing {key_path}: {e}")
    print("Context menu uninstalled.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        unregister_context_menu()
    else:
        register_context_menu()
