#!/usr/bin/env python


import sys
import time
from functools import partial

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types

from spsaitActor.utils import threaded, formatException


class CalibCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "calib"
        self.vocab = [
            ('background', '<nb> <exptime> [@(blue|red)] [force]', self.doBackground),
            ('bias', '<nbias> [@(blue|red)]', self.doBias),
            ('dark', '<ndarks> <exptime> [@(blue|red)]', self.doDarks),
            ('calib', '[<nbias>] [<ndarks>] [<exptime>] [@(blue|red)]', self.doBasicCalib),
            ('imstab',
             '<exptime> <nb> <delay> [@(neon|hgar|xenon)] [@(blue|red)] [<attenuator>] [<duplicate>] [switchOff] [force]',
             self.doImstab),
            ('expose',
             'arcs <exptime> [@(neon|hgar|xenon|krypton)] [<attenuator>] [@(blue|red)] [<duplicate>] [switchOff] [force]',
             self.doArc),
            ('expose', 'flats <exptime> [<attenuator>] [@(blue|red)] [<duplicate>] [switchOff] [force]', self.doArc),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_calib", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("nb", types.Int(), help="Number of exposure"),
                                        keys.Key("ndarks", types.Int(), help="Number of darks"),
                                        keys.Key("nbias", types.Int(), help="Number of bias"),
                                        keys.Key("delay", types.Int(), help="delay in sec"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of exposure per tempo(1 is default)"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def doBackground(self, cmd):
        e = False
        arm = ''
        cmdKeys = cmd.cmd.keywords
        dcbKeys = self.actor.models['dcb']

        exptime = cmdKeys['exptime'].values[0]
        nb = cmdKeys['nb'].values[0]
        force = True if "force" in cmdKeys else False

        arm = 'red' if 'red' in cmdKeys else arm
        arm = 'blue' if 'blue' in cmdKeys else arm

        if exptime <= 0:
            raise Exception("exptime must be > 0")
        if nb <= 0:
            raise Exception("nb > 0 ")

        sequence = self.controller.noLight()
        self.actor.processSequence(self.name, cmd, sequence)

        if not force:
            flux = dcbKeys.keyVarDict['photodiode'].getValue()
            if np.isnan(flux) or flux > 2e-3:
                raise Exception("Flux is not null")

        sequence = self.controller.background(exptime, nb, arm)
        self.actor.processSequence(self.name, cmd, sequence)

        cmd.finish("text='Background Sequence is over'")

    @threaded
    def doDarks(self, cmd):

        cmdKeys = cmd.cmd.keywords
        ndarks = cmdKeys['ndarks'].values[0]
        exptime = cmdKeys['exptime'].values[0]

        arms = ['blue', 'red']
        arms = arms[1:] if 'red' in cmdKeys else arms
        arms = arms[:1] if 'blue' in cmdKeys else arms

        ccds = [self.actor.arm2ccd[arm] for arm in arms]

        if exptime <= 0:
            raise Exception("exptime must be > 0")
        if ndarks <= 0:
            raise Exception("ndarks > 0 ")

        for ccd in ccds:
            sequence = self.controller.dark(ccd, exptime, ndarks)
            ccdThread = self.actor.controllers[ccd]
            ccdThread.showOn = True
            ccdThread.putMsg(partial(self.actor.processSequence, self.name, cmd, sequence))

        while not self.actor.jobsDone:
            time.sleep(1)

        cmd.finish("text='Dark Sequence is over'")

    @threaded
    def doBias(self, cmd):

        cmdKeys = cmd.cmd.keywords
        nbias = cmdKeys['nbias'].values[0]

        arms = ['blue', 'red']
        arms = arms[1:] if 'red' in cmdKeys else arms
        arms = arms[:1] if 'blue' in cmdKeys else arms

        ccds = [self.actor.arm2ccd[arm] for arm in arms]

        if nbias <= 0:
            raise Exception("nbias > 0 ")
        for ccd in ccds:
            sequence = self.controller.bias(ccd, nbias)
            ccdThread = self.actor.controllers[ccd]
            ccdThread.showOn = True
            ccdThread.putMsg(partial(self.actor.processSequence, self.name, cmd, sequence))

        while not self.actor.jobsDone:
            time.sleep(1)

        cmd.finish("text='Bias Sequence is over'")

    @threaded
    def doBasicCalib(self, cmd):
        cmdKeys = cmd.cmd.keywords

        ndarks = cmdKeys['ndarks'].values[0] if 'ndarks' in cmdKeys else 5
        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else 900
        nbias = cmdKeys['nbias'].values[0] if 'nbias' in cmdKeys else 15

        arms = ['blue', 'red']
        arms = arms[1:] if 'red' in cmdKeys else arms
        arms = arms[:1] if 'blue' in cmdKeys else arms

        ccds = [self.actor.arm2ccd[arm] for arm in arms]

        if exptime <= 0:
            raise Exception("exptime must be > 0")
        if ndarks <= 0:
            raise Exception("ndarks > 0 ")
        if nbias <= 0:
            raise Exception("nbias > 0 ")
        for ccd in ccds:
            sequence = self.controller.calibration(ccd, nbias, ndarks, exptime)
            ccdThread = self.actor.controllers[ccd]
            ccdThread.showOn = True
            ccdThread.putMsg(partial(self.actor.processSequence, self.name, cmd, sequence))

        while not self.actor.jobsDone:
            time.sleep(1)

        cmd.finish("text='Basic calib Sequence is over'")

    @threaded
    def doImstab(self, cmd):
        optArgs = []
        e = False

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        exptime = cmdKeys['exptime'].values[0]
        nb = cmdKeys['nb'].values[0]
        delay = cmdKeys['delay'].values[0]
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        switchOff = True if "switchOff" in cmdKeys else False

        optArgs = ['red'] if 'red' in cmdKeys else optArgs
        optArgs = ['blue'] if 'blue' in cmdKeys else optArgs

        optArgs += (['force'] if "force" in cmdKeys else [])

        arc = None
        arc = "neon" if "neon" in cmdKeys else arc
        arc = "hgar" if "hgar" in cmdKeys else arc
        arc = "xenon" if "xenon" in cmdKeys else arc

        if exptime <= 0:
            raise Exception("exptime must be > 0")
        if nb <= 1:
            raise Exception("nb > 1 ")
        if delay <= 0:
            raise Exception("delay > 0 ")
        if duplicate <= 0:
            raise Exception("duplicate > 0 ")

        try:
            sequence = self.controller.imstability(exptime, nb, delay, arc, duplicate, attenCmd, optArgs)
            self.actor.processSequence(self.name, cmd, sequence)
            msg = 'Image stability Sequence is over'

        except Exception as e:
            msg = formatException(e, sys.exc_info()[2])

        if arc is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arc, timeLim=60, forUserCmd=cmd)

        ender = cmd.fail if e else cmd.finish
        ender("text='%s'" % msg)

    @threaded
    def doArc(self, cmd):
        optArgs = []
        e = False

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        exptime = cmdKeys['exptime'].values[0]
        switchOff = True if "switchOff" in cmdKeys else False
        attenCmd = "attenuator=%i" % cmdKeys['attenuator'].values[0] if "attenuator" in cmdKeys else ""
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        optArgs = ['red'] if 'red' in cmdKeys else optArgs
        optArgs = ['blue'] if 'blue' in cmdKeys else optArgs

        optArgs += (['force'] if "force" in cmdKeys else [])

        arc = None
        arc = "neon" if "neon" in cmdKeys else arc
        arc = "hgar" if "hgar" in cmdKeys else arc
        arc = "xenon" if "xenon" in cmdKeys else arc
        arc = "krypton" if "krypton" in cmdKeys else arc
        arc = "halogen" if "flats" in cmdKeys else arc

        if exptime <= 0:
            raise Exception("exptime must be > 0")
        if duplicate <= 0:
            raise Exception("duplicate > 0 ")

        try:
            sequence = self.controller.arcs(exptime, arc, duplicate, attenCmd, optArgs)
            self.actor.processSequence(self.name, cmd, sequence)
            msg = 'Arcs Sequence is over'

        except Exception as e:
            msg = formatException(e, sys.exc_info()[2])

        if arc is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arc, timeLim=60, forUserCmd=cmd)

        ender = cmd.fail if e else cmd.finish
        ender("text='%s'" % msg)
