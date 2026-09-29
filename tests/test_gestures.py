from src.models import Gesture, GestureEvent
from src.vision.gesture_controller import GestureController
from src.vision.gesture_detector import GestureDetector, Point


def make_hand(open_fingers: bool = True, pinch: float | None = None) -> list[Point]:
    points = [Point(0.5, 0.8) for _ in range(21)]
    points[0] = Point(0.5, 0.8)
    points[5] = Point(0.40, 0.62)
    points[9] = Point(0.48, 0.60)
    points[13] = Point(0.56, 0.62)
    points[17] = Point(0.64, 0.66)
    for tip, pip, mcp, x in ((8, 6, 5, 0.40), (12, 10, 9, 0.48), (16, 14, 13, 0.56), (20, 18, 17, 0.64)):
        points[mcp] = Point(x, 0.62)
        points[pip] = Point(x, 0.48 if open_fingers else 0.70)
        points[tip] = Point(x, 0.28 if open_fingers else 0.76)
    points[4] = Point(0.23 if pinch is None else 0.40 + pinch, 0.28 if open_fingers else 0.76)
    return points


def test_open_palm_is_play_pause() -> None:
    event = GestureDetector().update(make_hand(), now=1.0)
    assert event.gesture is Gesture.PLAY_PAUSE


def test_folded_hand_pinches_for_volume() -> None:
    detector = GestureDetector()
    low = detector.update(make_hand(False, 0.02), now=1.0)
    high = detector.update(make_hand(False, 0.21), now=1.1)
    assert low.gesture is Gesture.VOLUME
    assert high.gesture is Gesture.VOLUME
    assert low.volume < high.volume


def test_swipe_emits_next_once() -> None:
    detector = GestureDetector("High")
    result = None
    for index, x in enumerate((0.25, 0.30, 0.36, 0.44, 0.55)):
        hand = make_hand(False, 0.03)
        hand[0] = Point(x, 0.8)
        result = detector.update(hand, now=1.0 + index * 0.08)
    assert result.gesture is Gesture.NEXT


def test_discrete_gesture_is_locked_until_clear() -> None:
    controller = GestureController(cooldown=1.0)
    palm = GestureEvent(Gesture.PLAY_PAUSE, 0.9)
    assert controller.process(palm, now=1.0) is not None
    assert controller.process(palm, now=2.2) is None
    controller.process(GestureEvent(Gesture.NONE), now=2.3)
    assert controller.process(palm, now=2.4) is not None


def test_cooldown_survives_brief_clear() -> None:
    controller = GestureController(cooldown=1.0)
    swipe = GestureEvent(Gesture.NEXT, 0.9)
    assert controller.process(swipe, now=1.0) is not None
    controller.process(GestureEvent(Gesture.NONE), now=1.1)
    assert controller.process(swipe, now=1.5) is None
    assert controller.process(swipe, now=2.1) is not None
