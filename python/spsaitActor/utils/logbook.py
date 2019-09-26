import sqlite3

from spsaitActor.utils import cleanStr


class Logbook:
    path = '///data/ait/'

    @staticmethod
    def newExperiment(dbname, experimentId, name, visitStart, visitEnd, seqtype, cmdStr, comments, startdate, cmdError,
                      anomalies=''):

        name = cleanStr(name)
        cmdStr = cleanStr(cmdStr)
        comments = cleanStr(comments)
        cmdError = cleanStr(cmdError)
        anomalies = cleanStr(anomalies)
        sqlRequest = """INSERT INTO Experiment VALUES (%i, "%s", %i, %i, "%s", "%s", "%s", "%s", "%s", "%s");""" % (
            experimentId,
            name,
            visitStart,
            visitEnd,
            seqtype,
            cmdStr,
            comments,
            anomalies,
            startdate,
            cmdError)
        Logbook.newRow(dbname=dbname, sqlRequest=sqlRequest)

    @staticmethod
    def newExposure(exposureId, site, visit, obsdate, exptime, exptype, quality='junk'):

        sqlRequest = """INSERT INTO Exposure VALUES ("%s","%s", %i, "%s", %.3f, "%s", "%s");""" % (exposureId,
                                                                                                   site,
                                                                                                   visit,
                                                                                                   obsdate,
                                                                                                   exptime,
                                                                                                   exptype,
                                                                                                   quality)
        Logbook.newRow(dbname='experimentLog', sqlRequest=sqlRequest)

    @staticmethod
    def newCamExposure(camExposureId, exposureId, smId, arm):
        sqlRequest = """INSERT INTO CamExposure VALUES ("%s","%s", %i, "%s");""" % (camExposureId,
                                                                                    exposureId,
                                                                                    smId,
                                                                                    arm)

        Logbook.newRow(dbname='experimentLog', sqlRequest=sqlRequest)

    @staticmethod
    def newRow(dbname, sqlRequest):
        conn = sqlite3.connect('%s/%s.db' % (Logbook.path, dbname))
        c = conn.cursor()
        try:
            c.execute(sqlRequest)
            conn.commit()

        except sqlite3.IntegrityError:
            pass

    @staticmethod
    def lastExperimentId(dbname):
        conn = sqlite3.connect('%s/%s.db' % (Logbook.path, dbname))
        c = conn.cursor()
        c.execute("""SELECT MAX(experimentId) FROM Experiment""")
        (experimentId,) = c.fetchone()
        experimentId = experimentId if experimentId is not None else 0

        return experimentId

    @staticmethod
    def setColumnValue(dbname, experimentId, column, value):
        sqlRequest = """UPDATE Experiment SET %s = "%s" WHERE experimentId=%i""" % (column,
                                                                                    cleanStr(value),
                                                                                    experimentId)
        Logbook.newRow(dbname=dbname, sqlRequest=sqlRequest)

    @staticmethod
    def buildCmdStr(dbname, experimentId):
        conn = sqlite3.connect('%s/%s.db' % (Logbook.path, dbname))
        c = conn.cursor()
        c.execute("""SELECT name, comments, cmdStr FROM Experiment WHERE experimentId=%i """ % experimentId)

        return c.fetchone()

