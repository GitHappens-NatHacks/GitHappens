"""Eye-relative gaze features from MediaPipe Face Mesh landmarks.

Measuring the iris position between the eye corners (instead of in the whole
camera frame) tracks eye movement and mostly ignores head movement.
Pure math: no camera, Qt or MediaPipe imports.
"""

from __future__ import annotations

from collections.abc import Sequence

Point = tuple[float, float]

# Face Mesh landmark ids. Index 0 and 3 of each eye list are the eye corners.
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]


def iris_ratio(corner_a: Point, corner_b: Point, iris: Point) -> Point:
    """Iris position in eye coordinates.

    u: 0 at corner_a, 1 at corner_b (along the corner axis).
    v: signed distance from the axis divided by eye width; positive = down in the image.
    """
    ax, ay = corner_b[0] - corner_a[0], corner_b[1] - corner_a[1]
    dx, dy = iris[0] - corner_a[0], iris[1] - corner_a[1]
    length_sq = ax * ax + ay * ay
    if length_sq < 1e-12:
        return (0.5, 0.0)
    u = (dx * ax + dy * ay) / length_sq
    v = (ax * dy - ay * dx) / length_sq
    return (u, v)


def _mean(points: Sequence[Point]) -> Point:
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)


def gaze_feature(points: Sequence[Point]) -> Point:
    """Average eye-relative iris position of both eyes.

    `points` are pixel coordinates indexed by Face Mesh landmark id (478 with refine_landmarks).
    """
    left = iris_ratio(points[LEFT_EYE[0]], points[LEFT_EYE[3]], _mean([points[i] for i in LEFT_IRIS]))
    right = iris_ratio(points[RIGHT_EYE[0]], points[RIGHT_EYE[3]], _mean([points[i] for i in RIGHT_IRIS]))
    return ((left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0)


# Head pointing: where the nose tip sits relative to the outer eye corners.
NOSE_TIP = 1
EYE_OUTER = (33, 263)  # left, right outer eye corners


def head_feature(points: Sequence[Point]) -> Point:
    """Head direction, independent of where the face is in the frame or how far away it is.

    x: nose tip along the eye line, 0 when facing the camera (+ = turned toward the right eye).
    y: nose tip below the eye line, in eye-widths (grows when tilting the head down).
    Turning/tilting the head moves this a lot more than the iris moves, so it is
    far steadier on a laptop webcam.
    """
    u, v = iris_ratio(points[EYE_OUTER[0]], points[EYE_OUTER[1]], points[NOSE_TIP])
    return (u - 0.5, v)
