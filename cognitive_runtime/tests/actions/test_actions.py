"""
Tests for RFC-0011 — Action Model

Coverage:
  1. Model Validation         — required fields, types, defaults, rejection of unknowns
  2. Serialization            — round-trip model_dump / model_validate, JSON mode
  3. Status Transitions       — valid forward transitions, invalid transitions rejected
  4. Immutable Behaviour      — frozen model cannot be mutated; with_status returns new copy
  5. Thread Safety            — concurrent reads from shared Action produce no races
  6. Event Publication        — all 6 event factories produce correct Event payloads
"""

import json
import threading
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cognitive_runtime.actions.events import (
    create_action_cancelled_event,
    create_action_completed_event,
    create_action_created_event,
    create_action_failed_event,
    create_action_queued_event,
    create_action_started_event,
)
from cognitive_runtime.actions.exceptions import (
    ActionValidationError,
    InvalidActionStatusTransitionError,
)
from cognitive_runtime.actions.models import (
    TERMINAL_ACTION_STATES,
    VALID_ACTION_TRANSITIONS,
    Action,
    ActionResultReference,
    ActionStatus,
    ActionType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_action() -> Action:
    """A valid action with only required fields populated."""
    return Action(
        plan_id="plan-001",
        step_id="step-001",
        type=ActionType.FILE_READ,
        target="/data/input.json",
    )


@pytest.fixture
def full_action() -> Action:
    """A valid action with every optional field populated."""
    ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    return Action(
        action_id="fixed-id-001",
        plan_id="plan-abc",
        step_id="step-xyz",
        type=ActionType.HTTP_POST,
        target="https://api.example.com/data",
        parameters={"body": {"key": "value"}, "timeout": 30},
        priority=10,
        status=ActionStatus.PENDING,
        created_at=ts,
        scheduled_at=ts,
        metadata={"requester": "planner_v1"},
    )


# ---------------------------------------------------------------------------
# 1. Model Validation
# ---------------------------------------------------------------------------


class TestModelValidation:
    def test_minimal_required_fields_accepted(self, minimal_action: Action) -> None:
        assert minimal_action.plan_id == "plan-001"
        assert minimal_action.step_id == "step-001"
        assert minimal_action.type == ActionType.FILE_READ
        assert minimal_action.target == "/data/input.json"

    def test_action_id_auto_generated(self, minimal_action: Action) -> None:
        assert minimal_action.action_id is not None
        assert len(minimal_action.action_id) == 36  # UUID4 format

    def test_two_actions_have_distinct_ids(self) -> None:
        a1 = Action(plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x")
        a2 = Action(plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x")
        assert a1.action_id != a2.action_id

    def test_default_status_is_pending(self, minimal_action: Action) -> None:
        assert minimal_action.status == ActionStatus.PENDING

    def test_default_priority_is_zero(self, minimal_action: Action) -> None:
        assert minimal_action.priority == 0

    def test_default_parameters_is_empty_dict(self, minimal_action: Action) -> None:
        assert minimal_action.parameters == {}

    def test_default_metadata_is_empty_dict(self, minimal_action: Action) -> None:
        assert minimal_action.metadata == {}

    def test_optional_timestamps_default_to_none(self, minimal_action: Action) -> None:
        assert minimal_action.scheduled_at is None
        assert minimal_action.started_at is None
        assert minimal_action.completed_at is None

    def test_created_at_auto_populated(self, minimal_action: Action) -> None:
        assert minimal_action.created_at is not None
        assert isinstance(minimal_action.created_at, datetime)

    def test_missing_plan_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Action(step_id="s", type=ActionType.FILE_READ, target="x")  # type: ignore[call-arg]

    def test_missing_step_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Action(plan_id="p", type=ActionType.FILE_READ, target="x")  # type: ignore[call-arg]

    def test_missing_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            Action(plan_id="p", step_id="s", target="x")  # type: ignore[call-arg]

    def test_missing_target_raises(self) -> None:
        with pytest.raises(ValidationError):
            Action(plan_id="p", step_id="s", type=ActionType.FILE_READ)  # type: ignore[call-arg]

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            Action(plan_id="p", step_id="s", type="INVALID_TYPE", target="x")  # type: ignore[arg-type]

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            Action(
                plan_id="p",
                step_id="s",
                type=ActionType.FILE_READ,
                target="x",
                status="NOT_A_STATUS",  # type: ignore[arg-type]
            )

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Action(
                plan_id="p",
                step_id="s",
                type=ActionType.FILE_READ,
                target="x",
                unknown_field="bad",  # type: ignore[call-arg]
            )

    def test_all_action_types_are_valid(self) -> None:
        for action_type in ActionType:
            action = Action(
                plan_id="p",
                step_id="s",
                type=action_type,
                target="anywhere",
            )
            assert action.type == action_type

    def test_all_action_statuses_are_valid(self) -> None:
        for status in ActionStatus:
            action = Action(
                plan_id="p",
                step_id="s",
                type=ActionType.CUSTOM,
                target="t",
                status=status,
            )
            assert action.status == status

    def test_action_result_reference_valid(self) -> None:
        ref = ActionResultReference(
            action_id="act-001",
            store="working_memory",
            key="result/act-001",
        )
        assert ref.action_id == "act-001"
        assert ref.store == "working_memory"
        assert ref.key == "result/act-001"
        assert ref.metadata == {}

    def test_action_result_reference_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ActionResultReference(
                action_id="a",
                store="s",
                key="k",
                bogus="field",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# 2. Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_model_dump_round_trip(self, minimal_action: Action) -> None:
        data = minimal_action.model_dump()
        restored = Action.model_validate(data)
        assert restored == minimal_action

    def test_model_dump_json_mode_round_trip(self, minimal_action: Action) -> None:
        data = minimal_action.model_dump(mode="json")
        restored = Action.model_validate(data)
        assert restored == minimal_action

    def test_model_json_round_trip(self, minimal_action: Action) -> None:
        raw = minimal_action.model_dump_json()
        parsed = json.loads(raw)
        restored = Action.model_validate(parsed)
        assert restored == minimal_action

    def test_full_action_round_trip(self, full_action: Action) -> None:
        data = full_action.model_dump(mode="json")
        restored = Action.model_validate(data)
        assert restored == full_action

    def test_serialized_type_is_string(self, minimal_action: Action) -> None:
        data = minimal_action.model_dump(mode="json")
        assert isinstance(data["type"], str)
        assert data["type"] == "FILE_READ"

    def test_serialized_status_is_string(self, minimal_action: Action) -> None:
        data = minimal_action.model_dump(mode="json")
        assert isinstance(data["status"], str)
        assert data["status"] == "PENDING"

    def test_none_timestamps_serialized_as_null(self, minimal_action: Action) -> None:
        data = minimal_action.model_dump(mode="json")
        assert data["scheduled_at"] is None
        assert data["started_at"] is None
        assert data["completed_at"] is None

    def test_result_reference_round_trip(self) -> None:
        ref = ActionResultReference(
            action_id="act-abc",
            store="fs",
            key="/tmp/result.json",
            metadata={"size_bytes": 512},
        )
        data = ref.model_dump(mode="json")
        restored = ActionResultReference.model_validate(data)
        assert restored == ref


# ---------------------------------------------------------------------------
# 3. Status Transitions
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    def test_pending_can_transition_to_queued(self, minimal_action: Action) -> None:
        assert minimal_action.can_transition_to(ActionStatus.QUEUED)

    def test_pending_can_be_cancelled(self, minimal_action: Action) -> None:
        assert minimal_action.can_transition_to(ActionStatus.CANCELLED)

    def test_pending_cannot_transition_to_running(self, minimal_action: Action) -> None:
        assert not minimal_action.can_transition_to(ActionStatus.RUNNING)

    def test_pending_cannot_transition_to_success(self, minimal_action: Action) -> None:
        assert not minimal_action.can_transition_to(ActionStatus.SUCCESS)

    def test_queued_can_transition_to_running(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.QUEUED,
        )
        assert action.can_transition_to(ActionStatus.RUNNING)

    def test_queued_can_be_cancelled(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.QUEUED,
        )
        assert action.can_transition_to(ActionStatus.CANCELLED)

    def test_running_can_succeed(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.RUNNING,
        )
        assert action.can_transition_to(ActionStatus.SUCCESS)

    def test_running_can_fail(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.RUNNING,
        )
        assert action.can_transition_to(ActionStatus.FAILED)

    def test_running_can_timeout(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.RUNNING,
        )
        assert action.can_transition_to(ActionStatus.TIMEOUT)

    def test_terminal_states_have_no_valid_targets(self) -> None:
        for terminal in TERMINAL_ACTION_STATES:
            action = Action(
                plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
                status=terminal,
            )
            assert action.is_terminal()
            for other in ActionStatus:
                assert not action.can_transition_to(other), (
                    f"Expected no transition from terminal {terminal} to {other}"
                )

    def test_valid_transitions_table_complete(self) -> None:
        """Every ActionStatus must appear as a key in the transitions table."""
        for status in ActionStatus:
            assert status in VALID_ACTION_TRANSITIONS, (
                f"{status} missing from VALID_ACTION_TRANSITIONS"
            )

    def test_is_terminal_for_non_terminal(self, minimal_action: Action) -> None:
        assert not minimal_action.is_terminal()

    def test_is_terminal_for_success(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.SUCCESS,
        )
        assert action.is_terminal()

    def test_is_terminal_for_failed(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.FAILED,
        )
        assert action.is_terminal()

    def test_is_terminal_for_cancelled(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.CANCELLED,
        )
        assert action.is_terminal()

    def test_is_terminal_for_timeout(self) -> None:
        action = Action(
            plan_id="p", step_id="s", type=ActionType.FILE_READ, target="x",
            status=ActionStatus.TIMEOUT,
        )
        assert action.is_terminal()


# ---------------------------------------------------------------------------
# 4. Immutable Behaviour
# ---------------------------------------------------------------------------


class TestImmutableBehaviour:
    def test_direct_field_assignment_raises(self, minimal_action: Action) -> None:
        with pytest.raises((ValidationError, TypeError)):
            minimal_action.status = ActionStatus.QUEUED  # type: ignore[misc]

    def test_direct_target_assignment_raises(self, minimal_action: Action) -> None:
        with pytest.raises((ValidationError, TypeError)):
            minimal_action.target = "/new/target"  # type: ignore[misc]

    def test_direct_priority_assignment_raises(self, minimal_action: Action) -> None:
        with pytest.raises((ValidationError, TypeError)):
            minimal_action.priority = 99  # type: ignore[misc]

    def test_with_status_returns_new_instance(self, minimal_action: Action) -> None:
        queued = minimal_action.with_status(ActionStatus.QUEUED)
        assert queued is not minimal_action

    def test_with_status_original_unchanged(self, minimal_action: Action) -> None:
        _ = minimal_action.with_status(ActionStatus.QUEUED)
        assert minimal_action.status == ActionStatus.PENDING

    def test_with_status_new_instance_has_correct_status(self, minimal_action: Action) -> None:
        queued = minimal_action.with_status(ActionStatus.QUEUED)
        assert queued.status == ActionStatus.QUEUED

    def test_with_status_preserves_all_other_fields(self, full_action: Action) -> None:
        queued = full_action.with_status(ActionStatus.QUEUED)
        assert queued.action_id == full_action.action_id
        assert queued.plan_id == full_action.plan_id
        assert queued.step_id == full_action.step_id
        assert queued.type == full_action.type
        assert queued.target == full_action.target
        assert queued.parameters == full_action.parameters
        assert queued.priority == full_action.priority
        assert queued.created_at == full_action.created_at
        assert queued.metadata == full_action.metadata

    def test_result_reference_direct_assignment_raises(self) -> None:
        ref = ActionResultReference(action_id="a", store="s", key="k")
        with pytest.raises((ValidationError, TypeError)):
            ref.store = "other_store"  # type: ignore[misc]

    def test_result_reference_model_copy_is_independent(self) -> None:
        ref = ActionResultReference(action_id="a", store="s", key="k")
        copy = ref.model_copy(deep=True)
        assert copy == ref
        assert copy is not ref


# ---------------------------------------------------------------------------
# 5. Thread Safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_reads_from_shared_action(self, minimal_action: Action) -> None:
        """
        Multiple threads reading from the same frozen Action must never observe
        inconsistent state. Since Action is immutable, this should trivially hold,
        but we verify it explicitly.
        """
        errors: list[Exception] = []
        results: list[ActionStatus] = []
        lock = threading.Lock()

        def reader() -> None:
            try:
                status = minimal_action.status
                with lock:
                    results.append(status)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Unexpected errors in threads: {errors}"
        assert len(results) == 50
        assert all(s == ActionStatus.PENDING for s in results)

    def test_concurrent_with_status_calls_produce_independent_copies(
        self, minimal_action: Action
    ) -> None:
        """
        Concurrent calls to with_status must each produce their own new Action
        without interfering with each other or the source.
        """
        copies: list[Action] = []
        lock = threading.Lock()

        def make_copy() -> None:
            copy = minimal_action.with_status(ActionStatus.QUEUED)
            with lock:
                copies.append(copy)

        threads = [threading.Thread(target=make_copy) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(copies) == 20
        assert all(c.status == ActionStatus.QUEUED for c in copies)
        # Original untouched
        assert minimal_action.status == ActionStatus.PENDING

    def test_concurrent_action_creation_produces_unique_ids(self) -> None:
        ids: list[str] = []
        lock = threading.Lock()

        def create() -> None:
            action = Action(
                plan_id="p", step_id="s", type=ActionType.CUSTOM, target="t"
            )
            with lock:
                ids.append(action.action_id)

        threads = [threading.Thread(target=create) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(ids) == 50
        assert len(set(ids)) == 50, "Duplicate action_ids detected under concurrency"


# ---------------------------------------------------------------------------
# 6. Event Publication
# ---------------------------------------------------------------------------


class TestEventPublication:
    def test_action_created_event(self, minimal_action: Action) -> None:
        event = create_action_created_event(minimal_action)
        assert event.event_type == "ActionCreated"
        assert event.source == "ActionModel"
        assert event.payload["action_id"] == minimal_action.action_id
        assert event.payload["plan_id"] == minimal_action.plan_id
        assert event.payload["step_id"] == minimal_action.step_id
        assert event.payload["type"] == minimal_action.type
        assert event.payload["target"] == minimal_action.target
        assert event.payload["priority"] == minimal_action.priority
        assert event.payload["status"] == minimal_action.status

    def test_action_queued_event(self) -> None:
        event = create_action_queued_event("act-999")
        assert event.event_type == "ActionQueued"
        assert event.source == "ActionModel"
        assert event.payload["action_id"] == "act-999"

    def test_action_started_event(self) -> None:
        event = create_action_started_event("act-999")
        assert event.event_type == "ActionStarted"
        assert event.source == "ActionModel"
        assert event.payload["action_id"] == "act-999"

    def test_action_completed_event(self) -> None:
        event = create_action_completed_event("act-999")
        assert event.event_type == "ActionCompleted"
        assert event.source == "ActionModel"
        assert event.payload["action_id"] == "act-999"

    def test_action_failed_event(self) -> None:
        event = create_action_failed_event("act-999", "Disk quota exceeded")
        assert event.event_type == "ActionFailed"
        assert event.source == "ActionModel"
        assert event.payload["action_id"] == "act-999"
        assert event.payload["reason"] == "Disk quota exceeded"

    def test_action_cancelled_event(self) -> None:
        event = create_action_cancelled_event("act-999")
        assert event.event_type == "ActionCancelled"
        assert event.source == "ActionModel"
        assert event.payload["action_id"] == "act-999"

    def test_all_events_have_unique_event_ids(self, minimal_action: Action) -> None:
        events = [
            create_action_created_event(minimal_action),
            create_action_queued_event(minimal_action.action_id),
            create_action_started_event(minimal_action.action_id),
            create_action_completed_event(minimal_action.action_id),
            create_action_failed_event(minimal_action.action_id, "err"),
            create_action_cancelled_event(minimal_action.action_id),
        ]
        ids = [e.event_id for e in events]
        assert len(set(ids)) == 6, "Events must have unique event_ids"

    def test_all_events_have_timestamps(self, minimal_action: Action) -> None:
        events = [
            create_action_created_event(minimal_action),
            create_action_queued_event(minimal_action.action_id),
            create_action_started_event(minimal_action.action_id),
            create_action_completed_event(minimal_action.action_id),
            create_action_failed_event(minimal_action.action_id, "err"),
            create_action_cancelled_event(minimal_action.action_id),
        ]
        for event in events:
            assert event.timestamp is not None

    def test_created_event_is_frozen(self, minimal_action: Action) -> None:
        """Events must be immutable — same guarantee as Actions."""
        event = create_action_created_event(minimal_action)
        with pytest.raises((ValidationError, TypeError)):
            event.event_type = "Mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 7. Exception Classes
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_action_validation_error_is_exception(self) -> None:
        err = ActionValidationError("bad field")
        assert isinstance(err, Exception)
        assert str(err) == "bad field"

    def test_invalid_transition_error_is_exception(self) -> None:
        err = InvalidActionStatusTransitionError("RUNNING → PENDING not allowed")
        assert isinstance(err, Exception)

    def test_both_inherit_from_action_error(self) -> None:
        from cognitive_runtime.actions.exceptions import ActionError
        assert issubclass(ActionValidationError, ActionError)
        assert issubclass(InvalidActionStatusTransitionError, ActionError)
