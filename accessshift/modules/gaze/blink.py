"""Blink detection from eye aspect ratio (EAR)."""

from collections import deque


def eye_aspect_ratio(eye):
    vertical_1 = ((eye[1][0] - eye[5][0]) ** 2 + (eye[1][1] - eye[5][1]) ** 2) ** 0.5
    vertical_2 = ((eye[2][0] - eye[4][0]) ** 2 + (eye[2][1] - eye[4][1]) ** 2) ** 0.5
    horizontal = ((eye[0][0] - eye[3][0]) ** 2 + (eye[0][1] - eye[3][1]) ** 2) ** 0.5
    if horizontal < 1e-6:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


class BlinkDetector:
    def __init__(self, ear_threshold=0.21, min_closed_frames=2, cooldown_frames=12):
        self.ear_threshold = ear_threshold
        self.min_closed_frames = min_closed_frames
        self.cooldown_frames = cooldown_frames
        self._closed = 0
        self._cooldown = 0
        self.history = deque(maxlen=30)

    def update(self, left_eye, right_eye):
        ear = (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2.0
        self.history.append(ear)
        intentional = False

        if self._cooldown > 0:
            self._cooldown -= 1
            return ear, intentional

        if ear < self.ear_threshold:
            self._closed += 1
        else:
            if self._closed >= self.min_closed_frames:
                intentional = True
                self._cooldown = self.cooldown_frames
            self._closed = 0

        return ear, intentional
