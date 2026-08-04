#######
Manager
#######

The Manager is the driving force behind Director. It is a Django application
that runs the actual `director site <https://director.tjhsst.edu>`_.
For the most part, we'll only talk about the ``sites`` app in this section.

The most useful models we use are the :class:`.Site` model and the :class:`.Operation` model.
The :class:`.Operation` model is just a representation of a task that needs to be done (ex: updating
an Nginx configuration).

.. tip::

  Given a :class:`.Operation`, you'll often see :func:`auto_run_operation_wrapper` being used to execute
  the operation. This context manager returns a :class:`.OperationWrapper`.
  The most important method you'll see used is :meth:`~.OperationWrapper.add_action`, which effectively schedules
  a callback (see the overloads for how to use it as a method vs as a decorator).
  Then, after running all of the callbacks, if all callbacks succeed, it will delete the original operation.


Communication with other parts
------------------------------
Let's talk a little bit about how the Manager communicates with other parts.
