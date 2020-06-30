import logs
from datetime import datetime
start_time = datetime.now()


def elog(info, name, ip):
    logs.error_log.error("%s-> %s: %s" % (ip.ljust(15, '-'), name, info))


def eelog(name='SVSL-040-Street_22-ASW1', ip='192.168.186.101'):

    elog('check massage!', name, ip)
    return 0


eelog()
logs.info_log.info("Просто какая-то информация")

print("Общее время выполнения скрипта: %s" % str(datetime.now() - start_time))

