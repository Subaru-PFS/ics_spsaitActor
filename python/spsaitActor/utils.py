import traceback as tb
from functools import partial


def threaded(func):
    def wrapper(self, *args, **kwargs):
        self.actor.allThreads[self.name].putMsg(partial(func, self, *args, **kwargs))

    return wrapper


def formatException(e, traceback):
    """ Format the caught exception as a string

    :param e: caught exception
    :param traceback: exception traceback
    """

    def clean(string):
        return str(string).replace("'", "").replace('"', "")

    return "%s %s %s" % (clean(type(e)), clean(type(e)(*e.args)), clean(tb.format_tb(traceback, limit=1)[0]))


class CmdSeq(object):
    def __init__(self, actor, cmdStr, timeLim=60, doRetry=False, tempo=1.0):
        object.__init__(self)
        self.actor = actor
        self.cmdStr = cmdStr
        self.timeLim = timeLim
        self.doRetry = doRetry
        self.tempo = tempo

    def build(self, cmd):
        return {"actor": self.actor,
                "cmdStr": self.cmdStr,
                "forUserCmd": cmd,
                "timeLim": self.timeLim,
                "doRetry": self.doRetry,
                }


class CryoException(Exception):
    def __init__(self, error="Abort cryo requested"):
        Exception.__init__(self, error)


class DetalignException(Exception):
    def __init__(self, error="Abort detalign requested"):
        Exception.__init__(self, error)


class ExposureException(Exception):
    def __init__(self, error="Abort exposure requested"):
        Exception.__init__(self, error)


class TestException(Exception):
    def __init__(self, error="Abort test requested"):
        Exception.__init__(self, error)
