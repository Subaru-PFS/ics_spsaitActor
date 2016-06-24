#!/usr/bin/env python

from actorcore.Actor import Actor


class SpsaitActor(Actor):
    def __init__(self, name, productName=None, configFile=None, debugLevel=30):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        Actor.__init__(self, name,
                       productName=productName,
                       configFile=configFile,
                       modelNames=['enu', 'ccd_r1'])


def main():
    actor = SpsaitActor('spsait', productName='spsaitActor')
    actor.run()


if __name__ == '__main__':
    main()
