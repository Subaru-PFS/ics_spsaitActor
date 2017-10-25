#!/usr/bin/env python

import time

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.utils import threaded, computeRate


class CryoCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "cryo"
        self.vocab = [
            ('leakback', '@(blue|red) [<duration>]', self.leakback),
            ('regeneration', '@(blue|red)', self.regeneration),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_cryo", (1, 1),
                                        keys.Key("duration", types.Int(),
                                                 help="Pressure rising test duration in minute"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @property
    def boolStop(self):
        return self.actor.boolStop[self.name]

    @threaded
    def leakback(self, cmd):
        cmdKeys = cmd.cmd.keywords
        arm = "blue" if "blue" in cmdKeys else "red"
        duration = 60 * (cmdKeys['duration'].values[0] if "duration" in cmdKeys else 15)

        xcuActor, xcuKeys = self.controller.xcuKeys(arm)
        xcuData = self.controller.xcuDatas[xcuActor]

        self.controller.sample(xcuActor, cmd=cmd)

        turboWasOn = True if 89900 < xcuData.turboSpeed < 90100 else False
        gvWasOpen = True if xcuData.gvPosition == "Open" and xcuData.gvControlState == "Open" else False
        ionPumpsWasOn = True if (xcuData.ionpump1On and xcuData.ionpump2On) else False
        tStart, pStart = time.time(), xcuData.pressure
        tlim = tStart + duration

        if duration < 15:
            raise Exception("Test duration is too short")

        if not ((turboWasOn and gvWasOpen) or (ionPumpsWasOn and not gvWasOpen)):
            raise Exception("No pumping")

        stopPumps = self.controller.stopPumps(xcuActor, ionPumpsWasOn, gvWasOpen)
        self.actor.processSequence(self.name, cmd, stopPumps)

        if not (xcuData.gvPosition == "Closed" and xcuData.gvControlState == "Closed"):
            raise Exception("Gatevalve is not closed !")

        if xcuData.ionpump1On or xcuData.ionpump2On:
            raise Exception("Ionpumps are not off !")

        if ionPumpsWasOn and not turboWasOn:
            th = xcuData.addThreshold(key="pressure",
                                      threshold=5e-6,
                                      vFail=5e-5,
                                      tlim=tlim,
                                      callback=self.actor.safeCall,
                                      kwargs={'actor': xcuActor, 'cmdStr': "ionpump on", 'forUserCmd': cmd})
        elif turboWasOn:
            th = xcuData.addThreshold(key="pressure",
                                      threshold=2e-3,
                                      vFail=0.5,
                                      tlim=tlim,
                                      callback=self.actor.safeCall,
                                      kwargs={'actor': xcuActor, 'cmdStr': "gatevalve open", 'forUserCmd': cmd})
        else:
            raise ValueError

        try:
            while not th.exitASAP:
                if turboWasOn and not (89900 < xcuData.turboSpeed < 90100):
                    raise Exception("Turbo is not spinning correctly anymore")

                if self.boolStop:
                    raise Exception("%s stop requested" % self.name.capitalize())
        except:
            th.exit()
            raise

        tEnd, pEnd = th.ret

        self.controller.sample(xcuActor, cmd=cmd)

        if ionPumpsWasOn and not turboWasOn:
            if not (xcuData.ionpump1On and xcuData.ionpump2On):
                raise Exception("Ionpumps haven't started correctly")
        else:
            if not (xcuData.gvPosition == "Open" and xcuData.gvControlState == "Open"):
                raise Exception("Gatevalve is not OPEN")

        cmd.inform("leakrate='%.5e Torr L s-1'" % computeRate(tStart, tEnd, pStart, pEnd))
        cmd.finish("text='leakback measurement is over'")

    @threaded
    def regeneration(self, cmd):
        cmdKeys = cmd.cmd.keywords
        arm = "blue" if "blue" in cmdKeys else "red"

        xcuActor, xcuKeys = self.controller.xcuKeys(arm)
        xcuData = self.controller.xcuDatas[xcuActor]

        self.controller.sample(xcuActor, cmd=cmd)

        gvWasClosed = True if xcuData.gvPosition == "Closed" and xcuData.gvControlState == "Closed" else False
        ionPumpsWasOn = True if (xcuData.ionpump1On and xcuData.ionpump2On) else False
        tStart, pStart = time.time(), xcuData.pressure

        if not gvWasClosed:
            raise Exception("Gatevalve is not closed")

        if not ionPumpsWasOn:
            raise Exception("Ionpumps are not started")

        startRoughing = self.controller.startRoughing()
        self.actor.processSequence(self.name, cmd, startRoughing)

        while self.controller.roughGauge > 1e-3:
            time.sleep(1)

        startTurbo = self.controller.startTurbo(xcuActor)
        self.actor.processSequence(self.name, cmd, startTurbo, doReset=False)

        while not (89900 < xcuData.turboSpeed < 90100):
            time.sleep(1)

        p0 = xcuData.pressure
        openGV = self.controller.openGV(xcuActor)
        self.actor.processSequence(self.name, cmd, openGV, doReset=False)

        while (xcuData.pressure / p0) > 0.8:
            time.sleep(1)

        regeneration = self.controller.regeneration(xcuActor)
