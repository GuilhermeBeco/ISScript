import json
from ctypes import *
import time
import requests
import os
from models import AQModel
import paho.mqtt.client as mqtt
import os
from urllib.parse import urlparse

listSensors = []

listAqsSemSensor = []
listToSend = []


# Define event callbacks
def on_connect(client, userdata, flags, rc):
    print("rc: " + str(rc))


def on_message(client, obj, msg):
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    idSensor = int(str(msg.payload))
    getSensors(idSensor)
    checkAQsSemSensor()


def on_publish(client, obj, mid):
    print("mid: " + str(mid))


def on_subscribe(client, obj, mid, granted_qos):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


def on_log(client, obj, level, string):
    print(string)


def convert(s):
    i = int(s, 16)  # convert from hex to a Python int
    cp = pointer(c_int(i))  # make this into a c integer
    fp = cast(cp, POINTER(c_float))  # cast the int pointer to a float pointer
    return fp.contents.value


def getValues(hexaString):
    listReverse = []
    for i in range(len(hexaString), 0, -1):
        if i % 2 == 1:
            s = hexaString[i - 1] + hexaString[i]
            listReverse.append(s)
    hexaStringOK = ""
    for l in listReverse:
        hexaStringOK = hexaStringOK + l
    listReverse.clear()
    return hexaStringOK


def sendPost(listToSend):
    dados = "[ "
    url = 'https://taes-webservice.herokuapp.com/api/aq'  # todo mudar o link e descomentar as 2 proximas linhas
    for a in listToSend:
        dados = dados + " { \"SensorID\": \"" + str(
            a.sensor) + "\", \"Temperature\": \"" + str(
            a.temp) + "\", \"Humidity\" : \"" + str(
            a.humidity) + "\", \"Battery\": \"" + str(
            a.batery) + "\", \"Timestamp\": \"" + str(a.timestamp) + "\" },"
    dados = dados[:-1]
    dados = dados + " ]"
    x = requests.post(url, data=dados)
    return x


def checkAQsSemSensor():
    for aq in listAqsSemSensor:
        if listSensors.__contains__(aq.sensor):
            listToSend.append(aq)


def getSensors(id):
    url = 'https://taes-webservice.herokuapp.com/api/sensors/all'  # todo mudar o link e descomentar as 2 proximas linhas
    dados = "{ \"SensorID\2: " + str(id) + " }"
    x = requests.post(url, data=dados)
    dataSensors = x.json()
    jArray = json.load(dataSensors)
    for s in jArray:
        listSensors.append(s['SensorID'])

    # todo also tenho de ajustar o id da burst no webservice


def main():
    mqttc = mqtt.Client()
    # Assign event callbacks
    mqttc.on_message = on_message
    mqttc.on_connect = on_connect
    mqttc.on_publish = on_publish
    mqttc.on_subscribe = on_subscribe
    url_str = os.environ.get('test.mosquitto.org', 'mqtt://localhost:1883')
    url = urlparse.urlparse(url_str)
    topic = 'newSensorsInsertIS'
    mqttc.connect(url.hostname, url.port)
    mqttc.subscribe(topic, 0)
    getSensors(0)
    with open('data.bin', 'rb') as fileB:
        listAqs = []
        listAqsFail = []

        responseJson = ""
        urlGet = 'https://taes-webservice.herokuapp.com/api/sensors'
        lastTimeSent = ""

        while True:
            if os.path.isfile('./lastSent.txt'):
                with open('lastSent.txt', 'r') as lastSentRead:
                    lastTimeSent = lastSentRead.read()
                    print("Timestamp lido do txt: {0}".format(lastTimeSent))
            binaryData = fileB.read(24)
            c = binaryData.hex()
            if c != "":
                # filtragem do hexa
                temperatureHex = c[8:16]
                humidityHex = c[16:24]
                timestampHex = c[32:40]

                sensorIdHexOK = c[:2]
                batteryHexOK = c[24:26]

                timestampHexOK = getValues(timestampHex)
                timestamp = int(timestampHexOK, 16)
                if int(lastTimeSent) < timestamp:
                    temperatureHexOK = getValues(temperatureHex)
                    temperature = convert(temperatureHexOK)

                    humidityHexOK = getValues(humidityHex)
                    humidity = convert(humidityHexOK)

                    sensorId = int(sensorIdHexOK, 16)
                    battery = int(batteryHexOK, 16)

                    aq = AQModel.AQModel(temperature, humidity, sensorId, timestamp, battery)
                    if listSensors.__contains__(aq.sensor):
                        listAqs.append(aq)
                    else:
                        listAqsSemSensor.append(aq)

                    if len(listAqs) == 10:
                        x = requests.get('https://taes-webservice.herokuapp.com/api/status')
                        if x.status_code == 200:
                            # send fails
                            if len(listAqsFail) != 0:
                                response = sendPost(listAqsFail)
                                if response.status_code == 200:
                                    listAqsFail.clear()

                            if len(listToSend) != 0:
                                response = sendPost(listToSend)
                                if response.status_code != 200:
                                    for a in listToSend:
                                        listAqsFail.append(a)
                                listToSend.clear()

                            response = sendPost(listAqs)
                            if response.status_code != 200:
                                for a in listAqs:
                                    listAqsFail.append(a)
                            else:
                                with open('lastSent.txt', 'w+') as lastSent:
                                    lastSent.write(str(listAqs[len(listAqs) - 1].timestamp))
                                    lastSent.close()
                            listAqs.clear()

                        else:
                            for a in listAqs:
                                listAqsFail.append(a)
            else:
                time.sleep(15)


if __name__ == "__main__":
    main()
