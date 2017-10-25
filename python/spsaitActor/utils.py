import sys
import traceback as tb
from functools import partial
import time
from actorcore.QThread import QThread

class Threshold(QThread):
    def __init__(self, actor, xcuData, name, threshold, vFail, tlim, callback, kwargs):
        QThread.__init__(self, actor, name, timeout=2)
        self.xcuData = xcuData
        self.threshold = threshold
        self.vFail = vFail
        self.tlim = tlim
        self.callback = callback
        self.kwargs = kwargs
        self.ret = None

        self.startUp()

    def handleTimeout(self):
        """| Is called when the thread is idle
        """

        if self.exitASAP:
            raise SystemExit()

        if self.vFail is not None and self.xcuData[self.name] >= self.vFail:
            self.ret = None, None
            self.exit()

        elif (self.xcuData[self.name] > self.threshold) or time.time() > self.tlim:
            self.ret = time.time(), self.xcuData[self.name]
            self.callback(**self.kwargs)
            self.exit()

    def exit(self):
        self.exitASAP = True


class xcuData(dict):
    def __init__(self, actor, xcu):
        dict.__init__(self)
        self.actor = actor
        self.xcuKeys = actor.models[xcu]

        for key in ['pressure', 'turboSpeed', 'gatevalve', 'ionpump1', 'ionpump2', 'coolerTemps']:
            keyvar = self.xcuKeys.keyVarDict[key]
            self[key] = None
            keyvar.addCallback(self.updateVals)

    def updateVals(self, keyvar):
        key = keyvar.name
        try:
            val = keyvar.getValue()
        except ValueError:
            val = None

        self[key] = val

    def addThreshold(self, key, threshold, vFail=None, tlim=None, callback=None, kwargs=None):
        th = Threshold(self.actor, self, key, threshold, vFail, tlim, callback, kwargs)
        return th

    @property
    def turboSpeed(self):
        return self['turboSpeed']

    @property
    def pressure(self):
        return self['pressure']

    @property
    def gvPosition(self):
        return self['gatevalve'][1]

    @property
    def gvControlState(self):
        return self['gatevalve'][2]

    @property
    def ionpump1On(self):
        return self['ionpump1'][0]

    @property
    def ionpump2On(self):
        return self['ionpump2'][0]

    @property
    def tip(self):
        return self['coolerTemps'][0]

    @property
    def coolerPower(self):
        return self['coolerTemps'][3]




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


class FailExposure(list):
    def __init__(self, ccd):
        list.__init__(self)
        self.extend([CmdSeq(ccd, "clearExposure"),
                     CmdSeq(ccd, "disconnect controller=fee", tempo=10),
                     CmdSeq(ccd, "connect controller=fee", tempo=5)])


def threaded(func):
    def tryfunc(self, cmd):
        try:
            return func(self, cmd)

        except Exception as e:
            cmd.fail("text='%s'" % formatException(e, sys.exc_info()[2]))
            return

    def wrapper(self, cmd):
        self.actor.controllers[self.name].putMsg(partial(tryfunc, self, cmd))

    return wrapper


def formatException(e, traceback):
    """ Format the caught exception as a string

    :param e: caught exception
    :param traceback: exception traceback
    """

    def clean(string):
        return str(string).replace("'", "").replace('"', "")

    return "%s %s %s" % (clean(type(e)), clean(type(e)(*e.args)), clean(tb.format_tb(traceback, limit=2)[-1]))



def computeRate(start, end, pressure1, pressure2):
    return 150 * (pressure2 - pressure1) / (end - start)



