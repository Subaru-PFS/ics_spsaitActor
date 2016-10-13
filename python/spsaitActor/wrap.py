from functools import partial

def threaded(func):
    def wrapper(self, *args, **kwargs):
        self.actor.myThread.putMsg(partial(func, self, *args, **kwargs))
    return wrapper
