# cbp 
Configuration Backup Project

[![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/downloads/release/python-360/) [![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/) [![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)

Суть данной работы является автоматизация сбора файлов конфигураций коммутаторов различных производителей и отправкой на FTP сервер.

Цель — обеспечить возможность восстановления файла конфигурации отдельного узла сети в случае его выхода из строя либо удаление/изменение самого файла.

#
Данная программа написанна:

* Руденко И.К.

* Петров А.С.

* Макаров В.Ю.

# Структура
backup.py - файл запуска 

all_switches.txt перечень оборудования

logs/ - папка для хранения логов

profiles/ - папка с профилями оборудования
