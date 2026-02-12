py -m pip install -r requirements.txt
py -m pip install pyinstaller
py -m PyInstaller --noconsole --onefile --name QR_Etiket_PDF app_gui.py
