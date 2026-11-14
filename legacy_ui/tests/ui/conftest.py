# Same headless Qt setup as the gaze tests: offscreen, one QApplication, no blocking chooser.
from tests.gaze.conftest import no_real_pointing_chooser, qapp  # noqa: F401
