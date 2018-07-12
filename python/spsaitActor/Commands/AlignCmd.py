#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from enuActor.utils.wrap import threaded


class AlignCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "align"
        self.vocab = [
            ('sac',
             'align <exptime> <focus> [<lowBound>] [<upBound>] [<nbPosition>] [<duplicate>] [<name>] [<comments>]',
             self.sacAlign),

            ('slit', 'throughfocus <exptime> <lowBound> <upBound> [<fiber>] [<nbPosition>] [<duplicate>] [<name>] [<comments>]',
             self.slitAlign),
            ('detector', 'throughfocus', self.detAlign),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_align", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("focus", types.Float(), help="sac ccd stage absolute position"),
                                        keys.Key("lowBound", types.Float(), help="lower bound for through focus"),
                                        keys.Key("upBound", types.Float(), help="upper bound for through focus"),
                                        keys.Key("nbPosition", types.Int(), help="Number of position"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="exposure duplicate per position (1 is default)"),
                                        keys.Key("fiber", types.String(),
                                                 help='fiber to aim'),
                                        keys.Key("name", types.String(),
                                                 help='experiment name'),
                                        keys.Key("comments", types.String(),
                                                 help='operator comments'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def sacAlign(self, cmd):
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        focus = cmdKeys['focus'].values[0]
        lowBound = cmdKeys['lowBound'].values[0] if 'lowBound' in cmdKeys else -300
        upBound = cmdKeys['upBound'].values[0] if 'upBound' in cmdKeys else 500
        nbPosition = cmdKeys['nbPosition'].values[0] if 'nbPosition' in cmdKeys else 2
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''

        sequence = self.controller.sacalign(exptime=exptime,
                                            focus=focus,
                                            lowBound=lowBound,
                                            upBound=upBound,
                                            nbPosition=nbPosition,
                                            duplicate=duplicate)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='SAC_Alignment',
                                   name=name,
                                   comments=comments)

        cmd.finish()

    @threaded
    def slitAlign(self, cmd):
        self.actor.resetSequence()

        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        lowBound = cmdKeys['lowBound'].values[0]
        upBound = cmdKeys['upBound'].values[0]
        nbPosition = cmdKeys['nbPosition'].values[0] if 'nbPosition' in cmdKeys else 2
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1
        targetedFiber = cmdKeys['fiber'].values[0] if 'fiber' in cmdKeys else False

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''

        sequence = self.controller.slitalign(exptime=exptime,
                                             targetedFiber=targetedFiber,
                                             lowBound=lowBound,
                                             upBound=upBound,
                                             nbPosition=nbPosition,
                                             duplicate=duplicate)

        for sub in sequence:
            print (sub.actor + ' ' + sub.cmdStr)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='Slit_Alignment',
                                   name=name,
                                   comments=comments)

        cmd.finish()

    @threaded
    def detAlign(self, cmd):
        pass
