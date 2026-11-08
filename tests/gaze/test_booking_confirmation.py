from PySide6.QtWidgets import QLabel, QPushButton

from accessshift.ui.booking_confirmation import BookingConfirmationDialog


def make():
    return BookingConfirmationDialog(who="Myself", visit="Check-up", when="Tomorrow 10:00")


def buttons(dlg):
    return {b.text(): b for b in dlg.findChildren(QPushButton)}


def test_confirmation_shows_details_and_two_choices(qapp):
    dlg = make()
    dlg.show()
    blob = "\n".join(w.text() for w in dlg.findChildren(QLabel))
    assert "You're booked!" in blob
    assert "Myself" in blob and "Check-up" in blob and "Tomorrow 10:00" in blob
    assert set(buttons(dlg)) == {"Start over", "Close"}
    assert "—" not in blob
    dlg.close()


def test_start_over_and_close_are_reported(qapp):
    dlg = make()
    dlg.show()
    buttons(dlg)["Start over"].click()
    assert dlg.choice == "start_over" and dlg.result() == BookingConfirmationDialog.DialogCode.Accepted
    dlg = make()
    dlg.show()
    buttons(dlg)["Close"].click()
    assert dlg.choice == "close"


def test_no_auto_close_so_the_person_chooses(qapp):
    dlg = make()
    assert dlg._timer is None
