import sys
import time
import traceback as tb
from functools import partial

import numpy as np
from actorcore.QThread import QThread


class Threshold(QThread):
    def __init__(self, actor, xcuData, name, ind, threshold, vFail, tlim, callback, kwargs, testfunc):
        QThread.__init__(self, actor, name, timeout=2)
        self.t0 = time.time() - 120
        self.xcuData = xcuData
        self.ind = ind
        self.threshold = threshold
        self.vFail = vFail
        self.tlim = tlim
        self.callback = callback
        self.kwargs = kwargs
        self.ret = None
        self.testfunc = testfunc

        self.startUp()

    def handleTimeout(self):
        """| Is called when the thread is idle
        """

        if self.exitASAP:
            raise SystemExit()

        if (time.time() - self.t0) > 120:
            cmd = self.kwargs['forUserCmd']
            info = 'in %i sec or ' % (self.tlim - time.time()) if self.tlim != np.inf else ""
            cmd.inform("text='Sending %s %s %sif %s[%i] %s than %g'" % (self.kwargs['actor'],
                                                                        self.kwargs['cmdStr'],
                                                                        info,
                                                                        self.name,
                                                                        self.ind,
                                                                        self.testfunc.__name__,
                                                                        self.threshold))

            self.t0 = time.time()
        if self.vFail is not None and self.testfunc(self.xcuData[self.name][self.ind], self.vFail):
            self.ret = None, None
            self.exit()

        elif self.testfunc(self.xcuData[self.name][self.ind], self.threshold) or time.time() > self.tlim:
            self.ret = time.time(), self.xcuData[self.name][self.ind]
            self.callback(**self.kwargs)
            self.exit()

    def exit(self):
        self.exitASAP = True


class xcuData(dict):
    def __init__(self, actor, xcu):
        dict.__init__(self)
        self.actor = actor
        self.xcuKeys = actor.models[xcu]
        self.thlist =[]

        for key in ['pressure', 'turboSpeed', 'gatevalve', 'ionpump1', 'ionpump2', 'coolerTemps',
                    'heaters', 'temps', 'roughPressure1']:
            keyvar = self.xcuKeys.keyVarDict[key]
            self[key] = None
            keyvar.addCallback(self.updateVals)

    def updateVals(self, keyvar):
        key = keyvar.name

        val = keyvar.getValue(doRaise=False)
        self[key] = val if type(val) is tuple else (val,)

    def addThreshold(self, key, threshold, ind=0, vFail=None, tlim=np.inf, callback=None, kwargs=None,
                     testfunc=np.greater):
        th = Threshold(self.actor, self, key, ind, threshold, vFail, tlim, callback, kwargs, testfunc)
        self.thlist.append(th)
        return th

    def waitFor(self, cmd, name, key, ind=0, inf=-np.inf, sup=np.inf, ti=1, refresh=120):
        t0 = time.time() - refresh
        while self[key][ind] is None or not (inf < self[key][ind] < sup):
            if self.actor.boolStop[name]:
                raise Exception("%s stop requested" % name.capitalize())
            time.sleep(ti)
            if (time.time() - t0) > refresh:
                if inf != -np.inf and sup != np.inf:
                    cmd.inform("text='Waiting %g < %s (%g) < %g'" % (inf, key, self[key][ind], sup))
                elif inf != -np.inf:
                    cmd.inform("text='Waiting %s (%g) > %g'" % (key, self[key][ind], inf))
                elif sup != np.inf:
                    cmd.inform("text='Waiting %s (%g) < %g'" % (key, self[key][ind], sup))
                t0 = time.time()

    def killThread(self):
        while self.thlist:
            th = self.thlist[0]
            try:
                th.exit()
            except:
                pass
            self.thlist.remove(th)

    @property
    def roughPressure(self):
        return self['roughPressure1'][0]

    @property
    def turboSpeed(self):
        return self['turboSpeed'][0]

    @property
    def pressure(self):
        return self['pressure'][0]

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

    @property
    def detectorBox(self):
        return self['temps'][0]

    @property
    def heaterSpider(self):
        return self['heaters'][0]

    @property
    def heaterCcd(self):
        return self['heaters'][1]


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
                     CmdSeq(ccd, "connect controller=fee")])


def roughing(state):
    if state not in ["start", "stop"]:
        raise ValueError
    state = "on" if state == "start" else "off"

    sequence = [CmdSeq("dcb", "aten switch %s channel=roughpump" % state),
                CmdSeq("dcb", "aten status")]

    return sequence


def turbo(xcuActor, state):
    if state not in ["start", "stop"]:
        raise ValueError

    sequence = [CmdSeq(xcuActor, "turbo %s" % state, doRetry=True),
                CmdSeq(xcuActor, "turbo status")]

    return sequence


def ionpumps(xcuActor, state):
    if state not in ["start", "stop"]:
        raise ValueError
    state = "on" if state == "start" else "off"

    sequence = [CmdSeq(xcuActor, "monitor controllers=ionpump period=0", doRetry=True, tempo=20),
                CmdSeq(xcuActor, "ionpump %s" % state, doRetry=True),
                CmdSeq(xcuActor, "ionpump status", doRetry=True),
                CmdSeq(xcuActor, "monitor controllers=ionpump period=15", doRetry=True)]

    return sequence


def gatevalve(xcuActor, state):
    if state not in ["open", "close"]:
        raise ValueError

    sequence = [CmdSeq(xcuActor, "gatevalve %s" % state, doRetry=True),
                CmdSeq(xcuActor, "gatevalve status")]

    return sequence


def heater(xcuActor, heater, state):
    if state not in ["on", "off"]:
        raise ValueError
    state = 'power=100' if state == "on" else "off"
    sequence = [CmdSeq(xcuActor, "heaters %s %s" % (heater, state), doRetry=True),
                CmdSeq(xcuActor, "heaters status")]

    return sequence


def cooler(xcuActor, state, setpoint=None):
    if state not in ["on", "off"]:
        raise ValueError
    state = 'on setpoint=%g' % setpoint if state == "on" else "off"
    tempo = 180 if state == "on" else 5
    sequence = [CmdSeq(xcuActor, "cooler %s" % state, doRetry=True, tempo=tempo),
                CmdSeq(xcuActor, "cooler status")]

    return sequence


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
