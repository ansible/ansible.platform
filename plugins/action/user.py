# plugins/action/user.py
from __future__ import annotations
from ansible.plugins.action import ActionBase
import os
import q

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        self._display.v("ansible.platform.user: action plugin start")

        args = dict(self._task.args)
        q(args)

        # Compute connection (env shown; replace with state-bus lookup if you want)
        base = args.get("base") or os.environ.get("AAP_BASE")
        token = args.get("token") or os.environ.get("AAP_TOKEN")
        verify = args.get("verify") if "verify" in args else os.environ.get("AAP_VERIFY", "")

        if base:
            args["base"] = base
        if token:
            args["token"] = token
        if verify != "":
            args["verify"] = verify

        # Call the real module with enriched args (no environ_update)
        q("Call _execute_module")
        result = self._execute_module(
            module_name="ansible.platform.user",  #  FQCN, not Python path
            module_args=args,
            task_vars=task_vars,
            wrap_async=False,
            tmp=tmp,
        )
        self._display.v("ansible.platform.user: action plugin end")
        return result





# from __future__ import annotations
# from ansible.plugins.action import ActionBase
# import os
# import q

# class ActionModule(ActionBase):
#     def run(self, tmp=None, task_vars=None):
#         q("Inside Action Module User")
#         # Example: ensure env-based auth defaults are present (centralize this logic)
#         env = dict(os.environ)
#         env.setdefault("AAP_VERIFY", env.get("AAP_VERIFY", ""))  # honor caller
#         # You could also pull from a local state-bus here and export AAP_BASE/AAP_TOKEN for the module.

#         # Then call the normal module execution path:
#         q("Calling super run")
#         result = super().run(tmp, task_vars)
#         return result
