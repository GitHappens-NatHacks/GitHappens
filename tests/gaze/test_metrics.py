from accessshift.modules.gaze.metrics import GazeMetrics


def test_accuracy_and_time():
    m = GazeMetrics()
    m.start_task(0)
    m.record_selection(100, "Neurology", "Neurology")
    m.record_selection(200, "Tue 10:00", "Tue 10:30")
    m.record_selection(300, None, "Book appointment")
    m.end_task(5000)
    assert m.summary() == {"selections": 3, "accuracy": 0.5, "task_ms": 5000}


def test_empty_summary():
    assert GazeMetrics().summary() == {"selections": 0, "accuracy": None, "task_ms": None}


def test_start_task_resets_counts():
    m = GazeMetrics()
    m.start_task(0)
    m.record_selection(100, None, "Myself")
    m.start_task(1000)
    assert m.summary() == {"selections": 0, "accuracy": None, "task_ms": None}
