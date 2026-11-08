import sys
from PySide6.QtWidgets import QApplication
from accessshift.modules.speech.widget import SpeechPanel

app = QApplication(sys.argv)
panel = SpeechPanel()
panel.setWindowTitle("Speech panel test")
panel.resize(600, 700)
panel.show()
app.aboutToQuit.connect(panel.speaker.close)
sys.exit(app.exec())