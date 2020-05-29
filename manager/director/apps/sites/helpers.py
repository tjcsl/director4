# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import contextlib
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union, overload

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.conf import settings

from ...utils.emails import send_email
from .models import Action, Operation, Site

ActionCallback = Callable[[Site, Dict[str, Any]], Iterator[Union[Tuple[str, str], str]]]


class OperationWrapper:
    def __init__(self, operation: Operation) -> None:
        self.operation = operation
        self.site = operation.site
        self.actions: List[Tuple[Action, ActionCallback]] = []

    @overload
    def add_action(  # pylint: disable=no-self-use # noqa
        self,
        name: str,
        *,
        slug: Optional[str] = None,
        user_recoverable: bool = False,
    ) -> Callable[[ActionCallback], ActionCallback]:
        ...

    @overload  # noqa
    def add_action(  # pylint: disable=no-self-use # noqa
        self,
        name: str,
        callback: ActionCallback,
        *,
        slug: Optional[str] = None,
        user_recoverable: bool = False,
    ) -> ActionCallback:
        ...

    def add_action(  # noqa
        self,
        name: str,
        callback: Optional[ActionCallback] = None,
        *,
        slug: Optional[str] = None,
        user_recoverable: bool = False,
    ) -> Union[ActionCallback, Callable[[ActionCallback], ActionCallback]]:
        created = False

        def wrap(callback: ActionCallback) -> ActionCallback:
            nonlocal created
            assert not created
            created = True

            action = Action.objects.create(
                operation=self.operation,
                slug=slug if slug is not None else callback.__name__,
                name=name,
                user_recoverable=user_recoverable,
            )

            self.actions.append((action, callback))

            return callback

        if callback is not None:
            return wrap(callback)
        else:
            return wrap

    def execute_operation(
        self,
        scope: Optional[Dict[str, Any]] = None,
        *,
        new_action_callback: Optional[Callable[[Action], None]] = None,
    ) -> bool:
        if scope is None:
            scope = {}

        self.operation.start_operation()

        for action, callback in self.actions:
            try:
                self.run_action(action, callback, scope, new_action_callback=new_action_callback)
            except BaseException as ex:  # pylint: disable=broad-except
                action.message += "{}: {}\nScope: {}".format(ex.__class__.__name__, ex, scope)
                action.result = False
                action.save()
                return False

        return True

    def run_action(
        self,
        action: Action,
        callback: ActionCallback,
        scope: Dict[str, Any],
        *,
        new_action_callback: Optional[Callable[[Action], None]] = None,
    ) -> None:
        action.start_action()

        if new_action_callback is not None:
            new_action_callback(action)

        for item in callback(self.site, scope):
            if isinstance(item, str):
                item = ("message", item)

            if not isinstance(item, tuple):
                raise TypeError("Invalid item type")

            if len(item) != 2:
                raise ValueError("Item length is incorrect")

            if item[0] == "message":
                action.message += item[1] + "\n"
            elif item[0] == "after_state":
                action.after_state = item[1]
            elif item[0] == "before_state":
                action.before_state = item[1]
            else:
                raise ValueError("Invalid item yielded")

            action.save()

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

    send_operation_updated_message(operation.site)

    def action_started(action: Action) -> None:  # pylint: disable=unused-argument
        send_operation_updated_message(operation.site)

    result = wrapper.execute_operation(scope, new_action_callback=action_started)

    if result:
        operation.action_set.all().delete()
        operation.delete()

    send_operation_updated_message(operation.site)


def send_operation_updated_message(site: Site) -> None:
    async_to_sync(get_channel_layer().group_send)(
        site.channels_group_name, {"type": "operation.updated"},
    )


def send_site_updated_message(site: Site) -> None:
    async_to_sync(get_channel_layer().group_send)(
        site.channels_group_name, {"type": "site.updated"},
    )


def send_new_site_email(*, user: Any, site: Site) -> None:
    send_email(
        text_template="emails/new_site_added.txt",
        html_template="emails/new_site_added.html",
        context={"site": site, "DJANGO_SETTINGS": settings},
        subject="You've been added to a new website!",
        emails=[user.email],
        bcc=False,
    )
