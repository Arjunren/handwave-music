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


def peace_sign() -> list[Point]:
    points = make_hand(False)
    for tip, pip, mcp, x in ((8, 6, 5, 0.40), (12, 10, 9, 0.48)):
        points[mcp] = Point(x, 0.62)
        points[pip] = Point(x, 0.48)
        points[tip] = Point(x, 0.28)
    return points


def volume_hand(index_x: float) -> list[Point]:
    points = make_hand(False)
    points[8] = Point(index_x, points[4].y)
    return points


def test_open_palm_requires_hold_for_play_pause() -> None:
    detector = GestureDetector()
    assert detector.update(make_hand(), now=1.0).gesture is Gesture.NONE
    assert detector.update(make_hand(), now=1.5).gesture is Gesture.NONE
    assert detector.update(make_hand(), now=1.9).gesture is Gesture.PLAY_PAUSE


def test_right_index_pinch_loads_for_two_seconds_then_fires_next_once() -> None:
    detector = GestureDetector()
    hand = pinched(8)
    started = detector.update(hand, "Right", now=1.0)
    halfway = detector.update(hand, "Right", now=2.0)
    completed = detector.update(hand, "Right", now=3.0)
    held = detector.update(hand, "Right", now=3.2)
    assert started.gesture is Gesture.NONE
    assert started.progress == 0.0
    assert halfway.gesture is Gesture.NONE
    assert halfway.progress == 0.5
    assert completed.gesture is Gesture.NEXT
    assert completed.progress == 1.0
    assert held.gesture is Gesture.NONE
    assert held.progress == 1.0


def test_left_index_pinch_requires_two_seconds_for_previous() -> None:
    detector = GestureDetector()
    assert detector.update(pinched(8), "Left", now=1.0).gesture is Gesture.NONE
    assert detector.update(pinched(8), "Left", now=2.9).gesture is Gesture.NONE
    assert detector.update(pinched(8), "Left", now=3.0).gesture is Gesture.PREVIOUS


def test_other_hand_peace_sign_enables_pinch_distance_volume() -> None:
    detector = GestureDetector()
    low_hands = [(peace_sign(), "Left", 0.9), (volume_hand(0.31), "Right", 0.8)]
    high_hands = [(peace_sign(), "Left", 0.9), (volume_hand(0.68), "Right", 0.8)]
    entered = detector.update_hands(low_hands, now=1.0)
    low = detector.update_hands(low_hands, now=1.1)
    high = detector.update_hands(high_hands, now=1.2)
    assert entered.gesture is Gesture.VOLUME_MODE
    assert low.gesture is Gesture.VOLUME
    assert high.gesture is Gesture.VOLUME
    assert low.volume < high.volume


def test_releasing_peace_sign_sets_volume_and_exits_mode() -> None:
    detector = GestureDetector()
    hands = [(peace_sign(), "Right", 0.9), (volume_hand(0.55), "Left", 0.8)]
    assert detector.update_hands(hands, now=1.0).gesture is Gesture.VOLUME_MODE
    assert detector.update_hands(hands, now=1.1).gesture is Gesture.VOLUME
    saved = detector.update_hands([(volume_hand(0.55), "Left", 0.8)], now=1.2)
    assert saved.gesture is Gesture.VOLUME_SAVE
    assert not detector.volume_mode


def test_two_hand_volume_takes_priority_over_track_pinch() -> None:
    detector = GestureDetector()
    hands = [(peace_sign(), "Right", 0.9), (pinched(8), "Left", 0.8)]
    assert detector.update_hands(hands, now=1.0).gesture is Gesture.VOLUME_MODE
    event = detector.update_hands(hands, now=3.5)
    assert event.gesture is Gesture.VOLUME
    assert event.volume == 0.0


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
