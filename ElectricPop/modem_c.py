#!/usr/bin/python3
# -*- coding: utf-8 -*-
from module.pmread import register_reading
from datetime import datetime
from cryptography.fernet import Fernet
import sqlite3 as sql
import os, re, time, serial, pickle
import RPi.GPIO as GPIO

cwd = os.path.dirname(os.path.realpath(__file__))
dbpath = cwd + "/config.db"
key = b'ztpn8wdO3ZNiNW3V9GZJlKWy8RioHnPC5-W5TQ0ZSEM='
cipher = Fernet(key)
counter = 0
connect_counter = 0

C_PWpin = 27  # chan C_PW dieu khien nguon cap cho RPI Sim808 Shield
PWKpin = 17  # chan PWK : bat/tat RPI Sim808 Shield
swPin = 12

# Cai dat cong ket noi Serial
ser = serial.Serial(port='/dev/ttyS0',
                    baudrate=9600,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    timeout=1)
# setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(C_PWpin, GPIO.OUT)
GPIO.setup(PWKpin, GPIO.OUT)
GPIO.setup(swPin, GPIO.OUT)

# Ham bat/tat modem
def GSM_Power():
    GPIO.output(PWKpin, 1)
    time.sleep(2)
    GPIO.output(PWKpin, 0)
    time.sleep(2)
    print("Switched\n")
    return

# Ham khoi tao cho modem
def GSM_Init():
    print("Khoi tao cho module SIM808... \n")
    ser.write(b'ATE0\r\n') 				# Tat che do phan hoi (Echo mode)
    time.sleep(1)
    ser.write(b'AT+IPR=9600\r\n') 		# Dat toc do truyen nhan du lieu 9600bps
    time.sleep(1)
    ser.write(b'AT+CMGF=1\r\n')			# Chon che do text mode
    time.sleep(1)
    ser.write(b'AT+CNMI=2,2\r\n') 		# Hien thi truc tiep noi dung tin nhan
    time.sleep(1)
    ser.write(b'AT+CGNSPWR=1\r\n')  # Bat GPS
    time.sleep(1)
    return

# KIem tra xem modem dang bat hay tat cho den khi da bat.
def GSM_Check():
    print("Check phan hoi tu GSM")
    ser.write(b"AT\r\n")
    time.sleep(1)
    res = ser.read(100)
    print(str(res, encoding="latin1"))
    if re.search("ERROR", str(res, encoding="latin1")) or res == b'':  #
        print("GSM da bi tat, dang bat lai...")
        GSM_Power()
        GSM_Check()
    else:
        print("GSM hien tai dang bat")
        GSM_Init()
        res = ser.readall()
        print(str(res, encoding="latin1"))

# Gui tin nhan
def GSM_MakeSMS(phone, text):
    print("Nhan tin...\n")
    cmd = "AT+CMGS=\"{}\"\r\n".format(phone)
    ser.write(bytes(cmd, encoding='latin1'))
    time.sleep(0.5)
    # res = ser.readall()
    # print(str(res, encoding="latin1")) 
    ser.write(bytes(text, encoding='latin1'))
    ser.write(b'\x1A')  # Gui Ctrl Z hay 26, 0x1A de ket thuc noi dung tin nhan va gui di
    # time.sleep(1)
    # res = ser.readall()
    # print(res)
    return

# Lay thong tin GPS
def GPS_GetInfo():
    print("*" * 40)
    print("Lay thong tin GPS")
    ser.write(b"AT+CGNSINF\r\n")
    time.sleep(1)
    info = ser.readall()
    CGNSINF = str(info, encoding="latin1").split(",")[3:5]
    print(CGNSINF)
    return {"GPS": ",".join(CGNSINF)}

# Ket noi toi serser de xac thuc
def SRV_Connect():
    print("Connecting to server...")
    ser.write(b"AT+CIPCLOSE\r\n")
    time.sleep(1)
    ser.write(b"AT+CIPSHUT\r\n")
    time.sleep(1)
    config = getrec("config", True)
    cmd = 'AT+CIPSTART="TCP","{}","{}"'.format(config["server"], config["port"])
    ser.write(bytes(cmd + '\r\n', encoding="latin1"))
    time.sleep(1)
    res = ser.readall()
    print(str(res, encoding="latin1"))
    #time.sleep(2)
    CIP_Send(pickle.dumps(config))

# Gui ban tin den server
def CIP_Send(packg):
    ser.write(bytes("AT+CIPSEND\r\n", encoding="latin1"))
    time.sleep(1)
    res = ser.readall()
    print(str(res, encoding="latin1"))
    ser.write(cipher.encrypt(packg))
    ser.write(b"\x1A")
##    time.sleep(1)
##    res = ser.readall()
##    print(str(res, encoding="latin1"))
    print()

# Lay cac ban ghi hoac 1 ban ghi trong sqlite
def getrec(table, mode = False):
    db = sql.connect(dbpath)
    db.row_factory = sql.Row
    mouse = db.cursor()
    mouse.execute("SELECT * FROM {}".format(table))
    if not mode:
        rows = mouse.fetchall()
        res = [dict(d) for d in rows]
    else:
        rows = mouse.fetchone()
        res = dict(rows)
    db.close()
    return res

# Xu li cac phan hoi tu server
def recv_package(decrespone):

    print(decrespone)

    def alarm():
        '''Nhan lenh gui tin nhan canh bao'''
        global counter
        print(counter)
        if decrespone.get("alarm") == True:
            if counter % 4 == 0:
                GSM_MakeSMS(decrespone["phone"], "Canh bao! \nPM: {}\nKhu vuc: {}".format(*list(decrespone.values())[2:]))
                print("Canh bao nguy hiem")
            counter += 1
        elif decrespone.get("alarm") == False:
                counter = 0
    def read_pm():
        '''Doc thong so va dong ngat mach'''
        if decrespone.get("read"):
            GPIO.output(swPin, decrespone["switch"]) # set high / low pin 12

            pack2send = dict()
            pminfo = getrec("powermeter")
            token = getrec("config", True)["token"]
            gps = GPS_GetInfo()
            uicosfi = [register_reading(d["ids"], 2, d["a"], d["a1"], d["a2"], d["a3"], d["vll"], d["vln"], d["v1"], d["v2"], d["v3"], d["v12"], d["v23"], d["v31"], d["pf"], d["pf1"], d["pf2"], d["pf3"]) for d in pminfo]
            pack2send["record"] = uicosfi
            pack2send["token"] = token
            pack2send.update(gps)
            packg = pickle.dumps(pack2send)
            CIP_Send(packg)

    exec(decrespone['func'])

def main():
    global connect_counter
    GSM_Check()
    try:
        SRV_Connect()
        start = time.time()
        while True:
            respone = ser.readlines()
            if respone:
                for item in respone:
                    try:
                        # Giai ma goi tin nhan dc tu cong Serial
                        decrypt_text = cipher.decrypt(item)
                        #
                        recv_package(pickle.loads(decrypt_text))
                    except Exception as e:
                        print(e)
                        pass
                start = time.time()

            end = time.time()
            if (end - start) >= 10:
                if connect_counter > 0 and connect_counter % 3 == 0:
                    GSM_Power()
                    time.sleep(2)
                    GSM_Check()
                    connect_counter = 0
                SRV_Connect()
                start = time.time()
                connect_counter += 1

    except KeyboardInterrupt:
        ser.write(b"AT+CIPCLOSE\r\n")
        ser.close()
    finally:
        print("End!\n")       
        GSM_Power()
        ser.close()
        GPIO.cleanup()

if __name__ == "__main__":
    main()
