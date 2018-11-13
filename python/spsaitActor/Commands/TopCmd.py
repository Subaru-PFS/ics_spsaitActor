#!/usr/bin/env python


import opscore.protocols.keys as keys
import opscore.protocols.types as types
from spsaitActor.logbook import Logbook


class TopCmd(object):
    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('abort', '', self.abort),
            ('logbook', '<dbname> <experimentId> [<name>] [<comments>] [<anomalies>]', self.setColumnValue)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("spsait_spsait", (1, 1),
                                        keys.Key("dbname", types.String(), help='dbname'),
                                        keys.Key("experimentId", types.Int(), help="experimentId to update"),
                                        keys.Key("name", types.String(), help='experiment name'),
                                        keys.Key("comments", types.String(), help='experiment comments'),
                                        keys.Key("anomalies", types.String(), help='anomalies message'),
                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report status and version; obtain and send current data"""

        cmd.inform('text="Present!"')
        cmd.finish()

    def abort(self, cmd):
        self.actor.doStop = True
        self.actor.abortShutters(cmd)

        cmd.finish("text='Aborting'")

    def setColumnValue(self, cmd):
        cmdKeys = cmd.cmd.keywords
        dbname = cmdKeys['dbname'].values[0]
        experimentId = cmdKeys['experimentId'].values[0]

        if 'name' in cmdKeys:
            Logbook.setColumnValue(dbname=dbname, experimentId=experimentId, column='name',
                                   value=cmdKeys['name'].values[0])

        if 'comments' in cmdKeys:
            Logbook.setColumnValue(dbname=dbname, experimentId=experimentId, column='comments',
                                   value=cmdKeys['comments'].values[0])

        if 'anomalies' in cmdKeys:
            Logbook.setColumnValue(dbname=dbname, experimentId=experimentId, column='anomalies',
                                   value=cmdKeys['anomalies'].values[0])

        cmd.finish()
