# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .models import Action, Operation, Site

ActionCallback = Callable[[Dict[str, Any]], Union[Dict[str, str], Tuple[str, ...]]]


class OperationWrapper:
    def __init__(self, site: Site, operation_type: str) -> None:
        self.site = site
        self.operation = Operation.objects.create(site=site, type=operation_type)
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

    def execute_operation(
        self, scope: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
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
                return False, scope

        return True, scope

    @staticmethod
    def run_action(action: Action, callback: ActionCallback, scope: Dict[str, Any]) -> None:
        action.start_action()

        result = callback(scope)

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
