import logging

# ------------------------------------CRITICAL ЛОГ------------------------------------------
critical_log = logging.getLogger('critical')
critical_log.setLevel(logging.INFO)
log_critical_file = logging.FileHandler("/home/admin/svi/logs/critical.log")
formatter = logging.Formatter('%(asctime)s | %(module)s -> %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_critical_file.setFormatter(formatter)
critical_log.addHandler(log_critical_file)
# -------------------------------------INFO ЛОГ------------------------------------------
info_log = logging.getLogger('info')
info_log.setLevel(logging.INFO)
log_info_file = logging.FileHandler("/home/admin/svi/logs/info.log")
formatter = logging.Formatter('%(asctime)s | %(module)s -> %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_info_file.setFormatter(formatter)
info_log.addHandler(log_info_file)
# -------------------------------------ERROR ЛОГ-----------------------------------------
error_log = logging.getLogger('error')
error_log.setLevel(logging.INFO)
log_error_file = logging.FileHandler("/home/admin/svi/logs/error.log")
formatter = logging.Formatter('%(asctime)s | %(module)s@%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_error_file.setFormatter(formatter)
error_log.addHandler(log_error_file)


# def elog(info):
#     error_log.error("%s|%s:%s" % ("{:15}".format(ip), name, info))

#elog("Дубликат %s файла конфигурации на коммутаторе не был удален!" % (name))

#critical_log.critical("СБОЙ!!!")
#info_log.info("Просто какая-то информация")
#error_log.error("MSAN | An error has happened!")

