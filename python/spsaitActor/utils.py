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
    def __init__(self, actor, cmdStr, timeLim=600, doRetry=False, tempo=5.0):
        object.__init__(self)
        self.actor = actor
        self.cmdStr = cmdStr
        self.timeLim = timeLim
        self.doRetry = doRetry
        self.tempo = tempo

    def build(self, cmd, keyStop):
        return {"actor": self.actor,
                "cmdStr": self.cmdStr,
                "forUserCmd": cmd,
                "timeLim": self.timeLim,
                "doRetry": self.doRetry,
                "keyStop": keyStop,
                }

def computeRate(start, end, pressure1, pressure2):

    return 150*(pressure2- pressure1)/((end-start).total_seconds())



class CryoException(Exception):
    def __init__(self, error="Abort cryo requested"):
        Exception.__init__(self, error)

class DetalignException(Exception):
    def __init__(self, error="Abort detalign requested"):
        Exception.__init__(self, error)

class DitherException(Exception):
    def __init__(self, error="Abort dither requested"):
        Exception.__init__(self, error)

class ExposeException(Exception):
    def __init__(self, error="Abort exposure requested"):
        Exception.__init__(self, error)

class CalibException(Exception):
    def __init__(self, error="Abort calib requested"):
        Exception.__init__(self, error)

class TestException(Exception):
    def __init__(self, error="Abort test requested"):
        Exception.__init__(self, error)


failExposure = [CmdSeq('ccd_r1', "clearExposure"),
                CmdSeq('ccd_r1', "disconnect controller=fee", tempo=20),
                CmdSeq('ccd_r1', "connect controller=fee", tempo=20)]