#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types

from enuActor.utils.wrap import threaded
from spsaitActor.sequencing import SubCmd


class ExposeCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.name = "expose"
        self.vocab = [
            ('expose',
             'arc <exptime> [<duplicate>] [<switchOn>] [<switchOff>] [<attenuator>] [force] [<cam>] [<cams>] [<name>] [<comments>] [<head>] [<tail>] [<drpFolder>]',
             self.doArc),
            ('expose',
             'flat <exptime> [<duplicate>] [switchOff] [<attenuator>] [force] [<cam>] [<cams>] [<name>] [<comments>] [<head>] [<tail>] [<drpFolder>]',
             self.doArc),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_expose", (1, 1),
                                        keys.Key("exptime", types.Float(), help="The exposure time"),
                                        keys.Key("duplicate", types.Int(),
                                                 help="exposure duplicate (1 is default)"),
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(), help='Attenuator value.'),
                                        keys.Key("cam", types.String(),
                                                 help='single camera to take exposure from'),
                                        keys.Key("cams", types.String() * (1,),
                                                 help='list of camera to take exposure from'),
                                        keys.Key("name", types.String(), help='experiment name'),
                                        keys.Key("comments", types.String(), help='operator comments'),
                                        keys.Key("head", types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key("tail", types.String() * (1,), help='cmdStr list to process after'),
                                        keys.Key("drpFolder", types.String(), help='detrend exposures to this folder'),
                                        )

    @property
    def controller(self):
        try:
            return self.actor.controllers[self.name]
        except KeyError:
            raise RuntimeError('%s controller is not connected.' % self.name)

    @threaded
    def doArc(self, cmd):
        cams = False
        self.actor.resetSequence()
        cmdKeys = cmd.cmd.keywords

        exptime = cmdKeys['exptime'].values[0]
        duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1

        if 'arc' in cmdKeys:
            exptype = 'arc'
            switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else False
            switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else False
        else:
            exptype = 'flat'
            switchOn = ['halogen']
            switchOff = ['halogen'] if 'switchOff' in cmdKeys else False

        attenuator = 'attenuator=%i' % cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else ''
        force = 'force' if 'force' in cmdKeys else ''

        cams = [cmdKeys['cam'].values[0]] if 'cam' in cmdKeys else cams
        cams = cmdKeys['cams'].values if 'cams' in cmdKeys else cams

        name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
        comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
        head = self.actor.subCmdList(cmdKeys['head'].values) if 'head' in cmdKeys else []
        tail = self.actor.subCmdList(cmdKeys['tail'].values) if 'tail' in cmdKeys else []
        drpFolder = cmdKeys['drpFolder'].values[0] if 'drpFolder' in cmdKeys else exptype
        doRaise = True if 'drpFolder' in cmdKeys else False

        if exptime <= 0:
            raise Exception("exptime must be > 0")

        if drpFolder:
            self.actor.safeCall(actor='drp',
                                cmdStr='set drpFolder=%s' % drpFolder,
                                forUserCmd=cmd,
                                doRaise=doRaise,
                                timeLim=5)

        if switchOn:
            head += [SubCmd(actor='dcb',
                            cmdStr="arc on=%s %s %s" % (','.join(switchOn), attenuator, force),
                            timeLim=300)]

        if switchOff:
            tail.insert(0, SubCmd(actor='dcb',
                                  cmdStr="arc off=%s" % ','.join(switchOff)))

        sequence = self.controller.arcs(exptype=exptype,
                                        exptime=exptime,
                                        duplicate=duplicate,
                                        cams=cams)

        self.actor.processSequence(cmd, sequence,
                                   seqtype='%ss' % exptype,
                                   name=name,
                                   comments=comments,
                                   head=head,
                                   tail=tail)

        cmd.finish()
