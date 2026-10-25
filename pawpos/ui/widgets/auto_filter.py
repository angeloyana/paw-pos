"""Coalesce filter edits and release Tk callbacks with their owning screen."""


class AutoFilter:
    def __init__(self, owner, refresh, *, text=(), choices=()):
        self.owner = owner
        self.refresh = refresh
        self.pending = None
        self.traces = []
        for variables, delay in ((text, 300), (choices, 0)):
            for variable in variables:
                token = variable.trace_add(
                    "write", lambda *_args, delay=delay: self.schedule(delay)
                )
                self.traces.append((variable, token))
        owner.bind("<Destroy>", self._destroy, add="+")

    def cancel(self):
        if self.pending is not None:
            self.owner.after_cancel(self.pending)
            self.pending = None

    def schedule(self, delay):
        self.cancel()
        self.pending = (
            self.owner.after(delay, self._run)
            if delay
            else self.owner.after_idle(self._run)
        )

    def _run(self):
        self.pending = None
        self.refresh()

    def _destroy(self, event):
        if event.widget == self.owner:
            self.cancel()
            for variable, token in self.traces:
                variable.trace_remove("write", token)
            self.traces.clear()
