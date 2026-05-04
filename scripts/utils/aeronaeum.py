import os, shutil

class Aeronaeum:
    def __init__(self):
        self.dirname: str = "Aeronaeum"
        self.dirpath: str = os.path.join(os.getcwd(), self.dirname)
        self.setup_aero_dir()
        self.downloaded_epubs: list[str] = [
            filename for filename in os.listdir(os.path.join(os.getcwd(), self.dirname)) 
            if filename.endswith(".epub")
        ]
        
    def setup_aero_dir(self) -> None:
        os.makedirs(self.dirname, exist_ok=True)
        if os.path.exists(self.dirpath):
            files = os.listdir(os.path.join(os.getcwd(), self.dirname))
            for file in files: 
                full_path_filepath = os.path.join(os.getcwd(), self.dirname, file)
                if os.path.isdir(full_path_filepath): 
                    shutil.rmtree(full_path_filepath)
        print(f'Deleted Incomplete Epub Directories...\n\n')
        return
 