# install_context.py
import sys
import os
import winreg
import subprocess

def get_forge_exe_path():
    # If running as bundled .exe, sys.executable is the .exe itself
    # If running as script, we need the path to Forge.exe (maybe we'll prompt)
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle
        return sys.executable
    else:
        # Development: we can use the script itself, but context menu needs .exe
        # We'll ask the user to provide path or assume Forge.exe is in the same folder.
        # For simplicity, we'll search for Forge.exe in current directory.
        exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Forge.exe')
        if os.path.exists(exe_path):
            return exe_path
        # If not found, prompt user
        return input("Enter full path to Forge.exe: ")

def register_context_menu():
    forge_path = get_forge_exe_path()
    if not os.path.exists(forge_path):
        print(f"Error: Forge.exe not found at {forge_path}")
        return

    # Define the subcommands and their arguments
    commands = {
        "compress_zip": {
            "verb": "Compress to ZIP",
            "cmd": f'"{forge_path}" compress --algo deflate --input "%V" --output "%V.zip"'
        },
        "compress_xz": {
            "verb": "Compress to XZ",
            "cmd": f'"{forge_path}" compress --algo lzma --input "%V" --output "%V.tar.xz"'
        },
        "compress_zst": {
            "verb": "Compress to ZST",
            "cmd": f'"{forge_path}" compress --algo zstd --input "%V" --output "%V.tar.zst"'
        },
        "extract": {
            "verb": "Extract with Forge",
            "cmd": f'"{forge_path}" extract --input "%V" --output-dir "%V_extracted"'
        }
    }

    # Key for files (*) and folders (Folder)
    key_paths = [
        r"*\shell\Forge",
        r"Folder\shell\Forge",
    ]

    for root_key in key_paths:
        # Create the main Forge key
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, root_key)
        winreg.SetValue(key, None, winreg.REG_SZ, "Forge")
        winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, "Forge")
        winreg.SetValueEx(key, "SubCommands", 0, winreg.REG_SZ, "compress_zip;compress_xz;compress_zst;extract")
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, forge_path)
        winreg.CloseKey(key)

    # Now create each subcommand
    for cmd_name, cmd_info in commands.items():
        sub_key_path = f"*\\shell\\Forge\\shell\\{cmd_name}"
        sub_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, sub_key_path)
        winreg.SetValue(sub_key, None, winreg.REG_SZ, cmd_info["verb"])
        # Command
        command_key = winreg.CreateKey(sub_key, "command")
        winreg.SetValue(command_key, None, winreg.REG_SZ, cmd_info["cmd"])
        winreg.CloseKey(command_key)
        winreg.CloseKey(sub_key)

        # Also for Folder
        folder_sub_key_path = f"Folder\\shell\\Forge\\shell\\{cmd_name}"
        folder_sub_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, folder_sub_key_path)
        winreg.SetValue(folder_sub_key, None, winreg.REG_SZ, cmd_info["verb"])
        folder_command_key = winreg.CreateKey(folder_sub_key, "command")
        winreg.SetValue(folder_command_key, None, winreg.REG_SZ, cmd_info["cmd"])
        winreg.CloseKey(folder_command_key)
        winreg.CloseKey(folder_sub_key)

    print("Context menu installed successfully!")

def unregister_context_menu():
    # Remove the keys
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
    print("Context menu uninstalled.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        unregister_context_menu()
    else:
        register_context_menu()
