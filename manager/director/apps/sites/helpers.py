# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import contextlib
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union

from .models import Action, Operation, Site

ActionCallback = Callable[[Site, Dict[str, Any]], Union[Dict[str, str], Tuple[str, ...]]]


class OperationWrapper:
    def __init__(self, operation: Operation) -> None:
        self.operation = operation
        self.site = operation.site
        self.actions: List[Tuple[Action, ActionCallback]] = []

    def add_action(
        self, name: str, *, slug: Optional[str] = None, equivalent_command: str = ""
    ) -> Callable[[ActionCallback], ActionCallback]:
        created = False

        def wrap(callback: ActionCallback) -> ActionCallback:
            nonlocal created
            assert not created
            created = True

            action = Action.objects.create(
                operation=self.operation,
                slug=slug if slug is not None else callback.__name__,
                name=name,
                equivalent_command=equivalent_command,
            )

            self.actions.append((action, callback))

            return callback

        return wrap

    def execute_operation(self, scope: Optional[Dict[str, Any]] = None) -> bool:
        if scope is None:
            scope = {}

        self.operation.start_operation()

        for action, callback in self.actions:
            try:
                self.run_action(action, callback, scope)
            except BaseException as ex:  # pylint: disable=broad-except
                action.message = "{}\nScope: {}".format(ex, scope)
                action.result = False
                action.save()
                return False

        return True

    def run_action(self, action: Action, callback: ActionCallback, scope: Dict[str, Any]) -> None:
        action.start_action()

        result = callback(self.site, scope)

        if isinstance(result, dict):
            action.before_state = result.get("before_state", "")
            action.after_state = result.get("after_state", "")
            action.message = result.get("message", "")
        elif isinstance(result, tuple):
            action.before_state, action.after_state, action.message, *_ = result + ("", "", "")
        else:
            raise TypeError("Action callback must return either a dictionary or a tuple")

        action.result = True
        action.save()


@contextlib.contextmanager
def auto_run_operation_wrapper(
    operation_id: int, scope: Dict[str, Any]
) -> Iterator[OperationWrapper]:
    """A context manager that, given an operation ID:
    1. Gets the Operation from the database (with .get(), so raises DoesNotExist if absent).
    2. Creates an OperationWrapper around the Operation.
    3. Passes the OperationWrapper to the with statement.
    4. Runs the OperationWrapper with the given scope when the with statement has finished.
    5. Deletes the Operation if it was successful.

    """

    operation = Operation.objects.get(id=operation_id)
    wrapper = OperationWrapper(operation)

    yield wrapper

    result = wrapper.execute_operation(scope)

    if result:
        operation.delete()
