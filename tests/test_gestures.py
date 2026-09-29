from src.models import Gesture, GestureEvent
from src.vision.gesture_controller import GestureController
from src.vision.gesture_detector import GestureDetector, Point


def make_hand(open_fingers: bool = True) -> list[Point]:
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
    points[4] = Point(0.23 if open_fingers else 0.30, 0.28 if open_fingers else 0.76)
    return points


def pinched(finger_tip: int) -> list[Point]:
    points = make_hand(False)
    thumb = points[4]
    points[finger_tip] = Point(thumb.x + 0.01, thumb.y)
    return points


def peace_sign(wrist_y: float = 0.5) -> list[Point]:
    points = make_hand(False)
    points[0] = Point(0.5, wrist_y)
    for tip, pip, mcp, x in ((8, 6, 5, 0.40), (12, 10, 9, 0.48)):
        points[mcp] = Point(x, 0.62)
        points[pip] = Point(x, 0.48)
        points[tip] = Point(x, 0.28)
    return points


def hand_at_height(wrist_y: float) -> list[Point]:
    points = make_hand()
    points[0] = Point(0.5, wrist_y)
    return points


def test_open_palm_requires_hold_for_play_pause() -> None:
    detector = GestureDetector()
    assert detector.update(make_hand(), now=1.0).gesture is Gesture.NONE
    assert detector.update(make_hand(), now=1.5).gesture is Gesture.NONE
    assert detector.update(make_hand(), now=1.9).gesture is Gesture.PLAY_PAUSE


def test_right_index_pinch_is_next_and_fires_once_per_pinch() -> None:
    detector = GestureDetector()
    hand = pinched(8)
    assert detector.update(hand, "Right", now=1.0).gesture is Gesture.NEXT
    assert detector.update(hand, "Right", now=1.1).gesture is Gesture.NONE


def test_left_index_pinch_is_previous() -> None:
    detector = GestureDetector()
    assert detector.update(pinched(8), "Left", now=1.0).gesture is Gesture.PREVIOUS


def enter_volume_mode(detector: GestureDetector, handedness: str = "Right") -> None:
    assert detector.update(peace_sign(), handedness, now=1.0).gesture is Gesture.NONE
    assert detector.update(peace_sign(), handedness, now=1.3).gesture is Gesture.NONE
    assert detector.update(peace_sign(), handedness, now=1.6).gesture is Gesture.VOLUME_MODE
    assert detector.volume_mode


def test_peace_sign_enters_volume_mode_and_hand_height_controls_level() -> None:
    detector = GestureDetector()
    enter_volume_mode(detector)
    low = detector.update(hand_at_height(0.78), "Right", now=1.7)
    high = detector.update(hand_at_height(0.18), "Right", now=1.8)
    assert low.gesture is Gesture.VOLUME
    assert high.gesture is Gesture.VOLUME
    assert low.volume < high.volume


def test_held_fist_freezes_volume_then_saves_and_exits() -> None:
    detector = GestureDetector()
    enter_volume_mode(detector, "Left")
    assert detector.update(hand_at_height(0.18), "Left", now=1.7).gesture is Gesture.VOLUME
    fist = make_hand(False)
    frozen = detector.update(fist, "Left", now=2.0)
    assert frozen.gesture is Gesture.NONE
    assert frozen.volume is None
    assert detector.update(fist, "Left", now=2.4).gesture is Gesture.NONE
    saved = detector.update(fist, "Left", now=2.7)
    assert saved.gesture is Gesture.VOLUME_SAVE
    assert not detector.volume_mode


def test_discrete_gesture_is_locked_until_clear() -> None:
    controller = GestureController(cooldown=1.0)
    palm = GestureEvent(Gesture.PLAY_PAUSE, 0.9)
    assert controller.process(palm, now=1.0) is not None
    assert controller.process(palm, now=2.2) is None
    controller.process(GestureEvent(Gesture.NONE), now=2.3)
    assert controller.process(palm, now=2.4) is not None


def test_cooldown_survives_brief_clear() -> None:
    controller = GestureController(cooldown=1.0)
    pinch = GestureEvent(Gesture.NEXT, 0.9)
    assert controller.process(pinch, now=1.0) is not None
    controller.process(GestureEvent(Gesture.NONE), now=1.1)
    assert controller.process(pinch, now=1.5) is None
    assert controller.process(pinch, now=2.1) is not None
