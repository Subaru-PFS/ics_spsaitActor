#!/usr/bin/env python

import time

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


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
            ('regeneration', '@(blue|red) [noleakback]', self.regeneration),
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

        cmd.inform("text='Pumps are OFF'")
        cmd.inform("text='leakback started'")

        if ionPumpsWasOn and not turboWasOn:
            th = xcuData.addThreshold(key="pressure",
                                      threshold=5e-6,
                                      vFail=2e-5,
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

        cmd.inform("text='Pump down restarted'")
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
        leaktime = 30 if "noleakback" in cmdKeys else 600
        refslope = (-20e-6/ 600)

        xcuActor, xcuKeys = self.controller.xcuKeys(arm)
        xcuData = self.controller.xcuDatas[xcuActor]
        roughData = self.controller.xcuDatas[self.actor.roughHack]

        self.controller.sample(xcuActor, cmd=cmd)

        gvWasClosed = True if xcuData.gvPosition == "Closed" and xcuData.gvControlState == "Closed" else False
        ionPumpsWasOn = True if (xcuData.ionpump1On and xcuData.ionpump2On) else False
        tStart, pStart = time.time(), xcuData.pressure

        if not gvWasClosed:
            raise Exception("Gatevalve is not closed")

        if not ionPumpsWasOn:
            raise Exception("Ionpumps are not started")

        cmd.inform("text='Regeneration process started'")

        cmd.inform("text='Starting Roughing pump ...'")
        self.actor.processSequence(self.name, cmd, roughing(state="start"))

        if not self.controller.roughPower:
            raise Exception("Roughing Pump is not powered ON !")

        roughData.waitFor(cmd, self.name, "roughPressure1", sup=1e-2)

        cmd.inform("text='Starting Turbo ...'")
        self.actor.processSequence(self.name, cmd, turbo(xcuActor, state="start"))

        xcuData.waitFor(cmd, self.name, "turboSpeed", inf=89900, sup=91100)

        if not (89900 < xcuData.turboSpeed < 90100):
            raise Exception("Turbo is not spinning correctly")

        cmd.inform("text='Turbo Started !'")

        tStart, pStart = time.time(), xcuData.pressure
        cmd.inform("text='Stopping Ionpumps ...'")
        self.actor.processSequence(self.name, cmd, ionpumps(xcuActor, state="stop"))
        if xcuData.ionpump1On or xcuData.ionpump2On:
            raise Exception("Ionpumps are still running")

        th = xcuData.addThreshold(key="pressure",
                                  threshold=2e-3,
                                  vFail=0.5,
                                  tlim=tStart + leaktime,
                                  callback=self.actor.safeCall,
                                  kwargs={'actor': xcuActor, 'cmdStr': "gatevalve open", 'forUserCmd': cmd})

        try:
            while not th.exitASAP:
                if not (89900 < xcuData.turboSpeed < 90100):
                    raise Exception("Turbo is not spinning correctly anymore")
                if not xcuData.pressure:
                    raise Exception("Ion gauge is not working anymore")
                if not roughData.roughPressure < 1e-2:
                    raise Exception("Roughing pressure is too high")
                if self.boolStop:
                    raise Exception("%s stop requested" % self.name.capitalize())
                time.sleep(2)
        except:
            th.exit()
            raise

        tEnd, pEnd = th.ret
        cmd.inform("leakrate='%.5e Torr L s-1'" % computeRate(tStart, tEnd, pStart, pEnd))

        xcuData.waitFor(cmd, self.name, "pressure", sup=pStart)
        for heatName in ['ccd', 'spider']:
            cmd.inform("text='Starting Heater %s...'" % heatName)
            self.actor.processSequence(self.name, cmd, heater(xcuActor, heatName, state="on"))

        if not xcuData.heaterCcd:
            raise Exception("Heater CCD is not powered ON")

        if not xcuData.heaterSpider:
            raise Exception("Heater spider is not powered ON")

        cmd.inform("text='Heaters powered ON !'")


        th1 = xcuData.addThreshold(key="temps",
                                   threshold=200,
                                   ind=0,
                                   callback=self.actor.safeCall,
                                   kwargs={'actor': xcuActor, 'cmdStr': "heaters ccd off", 'forUserCmd': cmd})

        th2 = xcuData.addThreshold(key="temps",
                                   threshold=150,
                                   ind=3,
                                   callback=self.actor.safeCall,
                                   kwargs={'actor': xcuActor, 'cmdStr': "heaters spider off", 'forUserCmd': cmd})

        try:
            self.actor.processSequence(self.name, cmd, cooler(xcuActor, state="off"))
            if xcuData.coolerPower:
                raise Exception("Cooler is not OFF")

            tCurrent, pCurrent = time.time(), xcuData.pressure
            while 1:
                if not (89900 < xcuData.turboSpeed < 90100):
                    raise Exception("Turbo is not spinning correctly anymore")
                if not xcuData.pressure:
                    raise Exception("Ion gauge is not working anymore")
                if self.boolStop:
                    raise Exception("%s stop requested" % self.name.capitalize())

                if (time.time() - tCurrent) > 20:
                    slope = ((xcuData.pressure - pCurrent)/ (time.time() - tCurrent))
                    if slope < refslope:
                        break
                    tCurrent, pCurrent = time.time(), xcuData.pressure
                    cmd.inform("text='Waiting for outgassing spike, slope(%g) < %g" % (slope, refslope))
                time.sleep(2)

        except Exception as e:
            xcuData.killThread()
            raise


        xcuData.waitFor(cmd, self.name, "pressure", sup=3e-6)

        self.actor.processSequence(self.name, cmd, cooler(xcuActor, state="on", setpoint=100))
        if not xcuData.coolerPower:
            raise Exception("Cooler is not ON")

        cmd.inform("text='Cooling down !'")
        th3 = xcuData.addThreshold(key="pressure",
                                   threshold=1e-6,
                                   testfunc=np.less,
                                   callback=self.actor.safeCall,
                                   kwargs={'actor': xcuActor, 'cmdStr': "ionpump on", 'forUserCmd': cmd})
        try:
            xcuData.waitFor(cmd, self.name, "coolerTemps", ind=2, sup=100)
            cmd.inform("text='Cooler Tip reached setpoint !'")

        except Exception as e:
            xcuData.killThread()
            raise

        if not (xcuData.ionpump1On and xcuData.ionpump2On):
            cmd.inform("text='Starting Ionpumps ...'")
            self.actor.processSequence(self.name, cmd, ionpumps(xcuActor, state="start"))

        if not (xcuData.ionpump1On and xcuData.ionpump2On):
            raise Exception("Ionpumps are not started")

        cmd.inform("text='Closing Gatevalve ...'")
        self.actor.processSequence(self.name, cmd, gatevalve(xcuActor, state="close"))
        if not (xcuData.gvPosition == "Closed" and xcuData.gvControlState == "Closed"):
            raise Exception("Gatevalve is not closed")

        cmd.inform("text='Stopping Turbo ...'")
        self.actor.processSequence(self.name, cmd, turbo(xcuActor, state="stop"))
        xcuData.waitFor(cmd, self.name, "turboSpeed", sup=1)

        if xcuData.turboSpeed:
            raise Exception("Turbo is still spinning")

        cmd.inform("text='Stopping Roughing pump ...'")
        self.actor.processSequence(self.name, cmd, roughing(state="stop"))

        if self.controller.roughPower:
            raise Exception("Roughing Pump is still powered ON !")



        cmd.finish("text='Regeneration process OK'")
