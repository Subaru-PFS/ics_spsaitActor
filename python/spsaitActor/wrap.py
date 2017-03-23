from functools import partial
import traceback as tb

def threaded(func):
    def wrapper(self, *args, **kwargs):
        self.actor.myThread[self.name].putMsg(partial(func, self, *args, **kwargs))
    return wrapper


def formatException(e, traceback):
    """ Format the caught exception as a string

    :param e: caught exception
    :param traceback: exception traceback
    """

    def clean(string):
        return str(string).replace("'", "").replace('"', "")

    return "%s %s %s" % (clean(type(e)), clean(type(e)(*e.args)), clean(tb.format_tb(traceback, limit=1)[0]))