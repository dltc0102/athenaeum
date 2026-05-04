import httpx, subprocess, os, shutil
from colorama import Fore as CFore
from colorama import Style as CStyle

def color_msg(color: str, msg: str) -> str:
    colors = {
        'black': CFore.BLACK,
        'blue': CFore.BLUE,
        'cyan': CFore.CYAN,
        'green': CFore.GREEN,
        'white': CFore.WHITE,
        'red': CFore.RED,
        'magenta': CFore.MAGENTA,
        'yellow': CFore.YELLOW,
        'lightblack': CFore.LIGHTBLACK_EX,
        'lightblue': CFore.LIGHTBLUE_EX,
        'lightcyan': CFore.LIGHTCYAN_EX,
        'lightgreen': CFore.LIGHTGREEN_EX,
        'lightmagenta': CFore.LIGHTMAGENTA_EX,
        'lightred': CFore.LIGHTRED_EX,
        'lightwhite': CFore.LIGHTWHITE_EX,
        'lightyellow': CFore.LIGHTYELLOW_EX,
    }
    return f"{colors[color.lower()]}{msg}{CStyle.RESET_ALL}"

def create_async_client(headers: dict[str, str]) -> httpx.AsyncClient:
    timeout = httpx.Timeout(connect=10.0, read=90.0, write=15.0, pool=10.0)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=15)
    return httpx.AsyncClient(headers=headers, timeout=timeout, limits=limits, follow_redirects=True)

def format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"
    
def get_folder_size(path: str) -> str:
    try:
        result = subprocess.run(
            ["du", "-sb", path],
            capture_output=True,
            text=True,
            check=True
        )
        size_bytes = int(result.stdout.split()[0])
        return format_size(size_bytes)
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"
 
async def reset_dir(npath: str) -> None:
    """deletes and recreates a directory at npath"""
    if os.path.exists(npath):
        shutil.rmtree(npath)
    if not os.path.exists(npath):
        os.mkdir(npath)

def print_mem(folder_name: str, folder_path: str = None) -> None:
    if not folder_path: folder_path = folder_name
    print(color_msg("lightcyan", f"[MEM] {folder_name}: {get_folder_size(folder_path)}"))