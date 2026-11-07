"""Eye-relative gaze features from MediaPipe Face Mesh landmarks.

Horizontal gaze uses iris position between the eye corners.
Vertical gaze uses iris offset from the corner line (lids often follow the iris
so an eyelid-only ratio collapses to mid-screen). A centered lid term is blended
in for extra range when the lids stay open.
Pure math: no camera, Qt or MediaPipe imports.
"""

from __future__ import annotations

from collections.abc import Sequence

Point = tuple[float, float]

# Face Mesh landmark ids. Index 0 and 3 of each eye list are the eye corners.
# Indices 1 and 2 are upper lid. Indices 4 and 5 are lower lid.
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]
# Mid-lid landmarks give a taller vertical socket than the EAR lid pairs alone.
LEFT_LID_MID = (159, 145)  # top, bottom
RIGHT_LID_MID = (386, 374)

# Stretch vertical so calibration can map top/bottom dots instead of parking on mid-row.
_VERTICAL_GAIN = 2.5
_LID_BLEND = 0.45


def axis_ratio(a: Point, b: Point, p: Point) -> float:
    """Projection of p onto the segment a→b as a 0..1 style ratio."""
    ax, ay = b[0] - a[0], b[1] - a[1]
    dx, dy = p[0] - a[0], p[1] - a[1]
    length_sq = ax * ax + ay * ay
    if length_sq < 1e-12:
        return 0.5
    return (dx * ax + dy * ay) / length_sq


def iris_ratio(corner_a: Point, corner_b: Point, iris: Point) -> Point:
    """Legacy helper kept for tests: u along corners, v perpendicular over eye width."""
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


def _lid_vertical(top: Point, bottom: Point, iris: Point) -> float:
    """0..1 iris position between lids. 0.5 is mid-opening."""
    return axis_ratio(top, bottom, iris)


def _eye_uv(
    eye_ids: list[int],
    iris_ids: list[int],
    lid_mid: tuple[int, int],
    points: Sequence[Point],
) -> Point:
    corner_a = points[eye_ids[0]]
    corner_b = points[eye_ids[3]]
    iris = _mean([points[i] for i in iris_ids])
    u = axis_ratio(corner_a, corner_b, iris)

    ax, ay = corner_b[0] - corner_a[0], corner_b[1] - corner_a[1]
    eye_w_sq = ax * ax + ay * ay
    if eye_w_sq < 1e-12:
        return (0.5, 0.0)
    # Positive when the iris sits below the corner chord (look down in image space).
    v_corner = (ax * (iris[1] - corner_a[1]) - ay * (iris[0] - corner_a[0])) / eye_w_sq

    top_mid = points[lid_mid[0]]
    bottom_mid = points[lid_mid[1]]
    top = _mean([points[eye_ids[1]], points[eye_ids[2]], top_mid])
    bottom = _mean([points[eye_ids[4]], points[eye_ids[5]], bottom_mid])
    v_lid = _lid_vertical(top, bottom, iris)

    # Corner chord stays put when lids chase the iris. Lid term is centered at 0.
    v = _VERTICAL_GAIN * (v_corner + _LID_BLEND * (v_lid - 0.5))
    return (u, v)


def gaze_feature(points: Sequence[Point]) -> Point:
    """Average eye-relative iris position of both eyes.

    `points` are pixel coordinates indexed by Face Mesh landmark id (478 with refine_landmarks).
    Returns (u, v) where u is left/right along the eye corners and v is up/down.
    """
    left = _eye_uv(LEFT_EYE, LEFT_IRIS, LEFT_LID_MID, points)
    right = _eye_uv(RIGHT_EYE, RIGHT_IRIS, RIGHT_LID_MID, points)
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
