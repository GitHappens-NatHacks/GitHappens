from PySide6.QtWidgets import QLabel, QPushButton

from accessshift.ui.booking_confirmation import BookingConfirmationDialog


def test_confirmation_shows_details_and_close(qapp):
    dlg = BookingConfirmationDialog(
        who="Myself",
        visit="Check-up",
        when="Tomorrow 10:00",
        auto_close_ms=0,
    )
    dlg.show()
    blob = "\n".join(w.text() for w in dlg.findChildren(QLabel))
    assert "You're booked!" in blob
    assert "Myself" in blob and "Check-up" in blob and "Tomorrow 10:00" in blob
    assert dlg.findChild(QPushButton).text() == "Close"
    dlg.close()


def test_confirmation_auto_closes(qapp):
    dlg = BookingConfirmationDialog(
        who="Myself",
        visit="Follow-up",
        when="Friday 11:30",
        auto_close_ms=30,
    )
    result = dlg.exec()
    assert result == BookingConfirmationDialog.DialogCode.Accepted
