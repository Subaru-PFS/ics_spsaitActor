#!/usr/bin/env python


from builtins import object
import sys
import time
from functools import partial

import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types

from spsaitActor.utils import threaded


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
            ('bias', '[<duplicate>] [<cam>] [<cams>]', self.doBias),
            ('dark', '<exptime> [<duplicate>] [<cam>] [<cams>]', self.doDarks),
            ('calib', '[<nbias>] [<ndarks>] [<exptime>] [<cam>] [<cams>]', self.doBasicCalib),

            ('imstab','', self.doImstab),
            ('background', '', self.doBackground),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_calib", (1, 1),
                                        keys.Key("duplicate", types.Int(),
                                                 help="duplicate number of exposure per tempo(1 is default)"),
                                        keys.Key("cam", types.String(),
                                                 help='single camera to take exposure from'),
                                        keys.Key("cams", types.String() * (1,),
                                                 help='list of camera to take exposure from'),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("ndarks", types.Int(), help="Number of darks"),
                                        keys.Key("nbias", types.Int(), help="Number of bias"),
                                        keys.Key("delay", types.Int(), help="delay in sec"),
                                        keys.Key("attenuator", types.Int(), help="optional attenuator value"),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def doBias(self, cmd):

        ex = False
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        cams = False
        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        sequence = self.controller.biases(duplicate=duplicate, cams=cams)
        self.actor.processSequence(cmd, sequence)

        cmd.finish()

    @threaded
    def doDarks(self, cmd):

        ex = False
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        cams = False
        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        exptime = cmdKeys['exptime'].values[0]

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        sequence = self.controller.darks(duplicate=duplicate, exptime=exptime, cams=cams)
        self.actor.processSequence(cmd, sequence)

        cmd.finish()

    @threaded
    def doBasicCalib(self, cmd):
        ex = False
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords
        cmdCall = self.actor.safeCall

        cams = False
        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        ndarks = cmdKeys['ndarks'].values[0] if 'ndarks' in cmdKeys else 5
        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else 900
        nbias = cmdKeys['nbias'].values[0] if 'nbias' in cmdKeys else 15

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        sequence = self.controller.calibration(nbias=nbias, ndarks=ndarks, exptime=exptime, cams=cams)
        self.actor.processSequence(cmd, sequence)

        cmd.finish()


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
            msg = self.actor.strTraceback(e)

        if arc is not None and switchOff:
            cmdCall(actor='dcb', cmdStr="%s off" % arc, timeLim=60, forUserCmd=cmd)

        ender = cmd.fail if e else cmd.finish
        ender("text='%s'" % msg)

