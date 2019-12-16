import json
from ctypes import *
import time
import requests
import os
from models import AQModel
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def convert(s):
    i = int(s, 16)  # convert from hex to a Python int
    cp = pointer(c_int(i))  # make this into a c integer
    fp = cast(cp, POINTER(c_float))  # cast the int pointer to a float pointer
    return fp.contents.value


def getValues(hexaString):
    # lista aux
    listReverse = []
    # percorre o hexa recebido do fim para o inicio (visto que os valores estão ao contrário)
    for i in range(len(hexaString), 0, -1):
        # verifica quando é um bloco hexadecimal (normalmente de 2 char)
        if i % 2 == 1:
            # constroi o bloco
            s = hexaString[i - 1] + hexaString[i]
            # guarda o bloco
            listReverse.append(s)
    # append do novo bloco
    hexaStringOK = ""
    for l in listReverse:
        hexaStringOK = hexaStringOK + l
    listReverse.clear()
    # return do novo bloco ordenado
    return hexaStringOK


def sendPost(listToSend):
    # preparação do array
    dados = "[ "
    url = 'https://localhost:44301/api/aq/burst'  # todo mudar o link e descomentar as 2 proximas linhas
    for a in listToSend:
        # escritura do json
        dados = dados + " { \"SensorID\": \"" + str(
            a.sensor) + "\", \"Temperature\": \"" + str(
            a.temp) + "\", \"Humidity\" : \"" + str(
            a.humidity) + "\", \"Battery\": \"" + str(
            a.batery) + "\", \"Timestamp\": \"" + str(a.timestamp) + "\" },"
    # remoção da virgula no ultimo valor (quando chega ao fim , ela não é pretendida)
    dados = dados[:-1]
    # fecha o array
    dados = dados + " ]"
    # send dos dados (o data mapeia a string para json)
    x = requests.post(url, data=dados,verify=False)
    # retorna toda a variavel de response
    return x


def main():
    with open('data.bin', 'rb') as fileB:
        listAqs = []
        listAqsFail = []
        lastTimeSent = ""
        # vars necessárias
        while True:
            # obter o ultimo timestamp enviado
            if os.path.isfile('./lastSent.txt'):
                with open('lastSent.txt', 'r') as lastSentRead:
                    lastTimeSent = lastSentRead.read()
                    print("Timestamp lido do txt: {0}".format(lastTimeSent))
            else:
                lastTimeSent="0"
            # leitura de um registo e conversão para hexa
            binaryData = fileB.read(24)
            c = binaryData.hex()
            # se a leitura não for vazia, irá processar os dados, senão vai fazer um sleep de 15 sec
            if c != "":
                # mapeamento do hexa (split da string c do index x ao index y (c[x:y]
                temperatureHex = c[8:16]
                humidityHex = c[16:24]
                timestampHex = c[32:40]
                # estes 2 não têm a necessidade de serem revertidos, já vêm na ordem certa
                sensorIdHexOK = c[:2]
                batteryHexOK = c[24:26]
                # obter o valor concreto do timestamp (ver comments na função)
                timestampHexOK = getValues(timestampHex)
                timestamp = int(timestampHexOK, 16)
                print(timestamp)
                # se o timestamp guardado for maior que o lido, não se processa os dados
                if int(lastTimeSent) < timestamp:
                    # Igual ao timestamp
                    temperatureHexOK = getValues(temperatureHex)
                    # convert(hex) é para converter de hexa para float
                    temperature = convert(temperatureHexOK)
                    # Igual ao timestamp
                    humidityHexOK = getValues(humidityHex)
                    humidity = convert(humidityHexOK)
                    # visto que já vêm na ordem, basta os converter
                    sensorId = int(sensorIdHexOK, 16)
                    battery = int(batteryHexOK, 16)
                    # set dos valores para um novo modelo e para uma lista
                    aq = AQModel.AQModel(temperature, humidity, sensorId, timestamp, battery)
                    listAqs.append(aq)
                    # len list=10 == 1m:30s
                    if len(listAqs) == 10:
                        # primeiro saber se o server está estável, senão todos os valores lidos irão para uma lista
                        # de fails e os dados continuaram a ser processados
                        x = requests.post('https://localhost:44301/api/ok',verify=False)
                        print("status = {0}".format(x.status_code))
                        x.status_code=200
                        if x.status_code == 200:
                            print("status Inside")
                            # send fails quando existem fails e o servidor está estável, os fails têm prioridade pois
                            # já lá deviam estar
                            if len(listAqsFail) != 0:
                                # send dos valores que retorna a resposta
                                response = sendPost(listAqsFail)
                                if response.status_code == 200:
                                    # se todos os valores foram inseridos, já não há necessidade de os guardar
                                    listAqsFail.clear()
                            # send oks
                            response = sendPost(listAqs)
                            # send dos valores
                            if response.status_code != 200:
                                print(response.content)
                                # se a resposta foi diferente de 200 (ex: o server caiu desde o ping até aqui)
                                # os valores são inseridos nos fails para na proxima eles sejam enviados
                                for a in listAqs:
                                    listAqsFail.append(a)
                            else:
                                # senão houve fails, será guardado o ultimo valor do timestamp para que seja comparado
                                # nos proximos processamentos de dados
                                print(response.content)
                                with open('lastSent.txt', 'w+') as lastSent:
                                    lastSent.write(str(listAqs[len(listAqs) - 1].timestamp))
                                    lastSent.close()
                            # em qualquer um dos casos, a lista tem de ser limpa para receber os novos dados
                            listAqs.clear()

                        else:
                            # se o server não está estável, guarda-se os dados nos fails
                            for a in listAqs:
                                listAqsFail.append(a)
                            listAqs.clear()
            else:
                time.sleep(15)


if __name__ == "__main__":
    main()
