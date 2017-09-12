from __future__ import print_function  # Python 2/3 compatibility
from flask import Flask, request, send_from_directory, redirect, render_template
from multiprocessing import Process
import boto3
from botocore.exceptions import ClientError
import json
import sys
import syslog
import time
import os
import requests
import urllib
import logging
import subprocess
import redis

# I really like logging. It makes me understand what my code is doing much better.
# It makes so much more sense than the ramblings "BossMan" goes on.
# Maybe this is a good idea if my pots are being smashed...
if 'LOG_LEVEL' in os.environ:
    logLevel = os.environ['LOG_LEVEL'].upper()
else:
    logLevel = "INFO"
logging.basicConfig(format='%(asctime)s %(levelname)s:\t%(message)s', level=getattr(logging, logLevel, None))


class Rental:
    def __init__(self):
        self.rentalId = ""

        # AWS Makes it really super simple to create a new Service Client.
        # I wish Kyle would take a page out of their book and make things around here this simple.
        self.sqs = boto3.client('sqs')
        self.redis = redis.from_url(os.environ['REDIS_URL'])
        self.queueUrl = os.environ['AWS_RENTAL_SQS_QUEUE']
        self.apiEndpointURL = os.environ['UNICORN_RENTAL_RETURN_ENDPOINT']

    #  The AWS Boto3 SDK has a built in method for polling SQS for Messages
    #  This makes it a lot easier to grab the max of 10 messages per request.
    def getMessageList(self):
        response = self.sqs.receive_message(
            QueueUrl=self.queueUrl,
            MaxNumberOfMessages=5,
            VisibilityTimeout=1,
            WaitTimeSeconds=20
        )
        return response

    # It's really important for me to return accurate rental durations.
    # If I don't then Kyle will definitely take away some my RSU assignments.
    def calculateRentalDuration(self, rentalId, returnTime):

        rentalTime = self.redis.hget(rentalId, 'rentalTime')
        if rentalTime is None:
            logging.warning("There is no rental with id [{}] in the database".format(rentalId))
            return 10000 - int(returnTime)

        rentalDuration = int(returnTime) - int(rentalTime)
        return rentalDuration

    # I don't want to process duplicate messages, or Kyle will take away my RSU Assignments.
    def removeMessage(self, receiptHandle):
        logging.info("Removing Message: {}".format(receiptHandle))
        try:
            self.sqs.delete_message(
                QueueUrl=self.queueUrl,
                ReceiptHandle=receiptHandle
            )
            return True
        except ClientError as e:
            logging.error("Error Deleting SQS Message: {}".format(e.response['Error']['Code']))
            if e.response['Error']['Code'] == "AWS.SimpleQueueService.Throttling":
                self.removeMessage(receiptHandle)

    def validateMessage(self, rentalId, receiptHandle):
        return True
        '''
        r = requests.get("{}/spaceinvaders/{}".format(self.apiEndpointURL, urllib.quote_plus(rentalId) ))
        if r.status_code == 200:
            logging.info("Message Validated: {}".format(rentalId))
            return True
        else:
            if not self.rampageDecryption():
                return True
            logging.info("Not Processing: {}".format(rentalId))
            self.removeMessage(receiptHandle)
            return False
        '''

    # For security reasons I needed to encrypt the customer information. I wrote a very simple binary to decrypt
    # the messages for me.
    def rampageDecryption(self):
        try:
            resp = subprocess.check_output("/usr/src/app/bin/rampage", stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            logging.error("There was an error when invoking the rampage Binary. Please Make sure it's runnable ( chmod +x )")
            logging.error("Error message: {}".format(e))
            return False
        if resp.rstrip() == "true":
            return True
        else:
            logging.error(resp.rstrip())
            return False

    # This is where I start the logical flow of processing the rental return messages from the SQS Queue.
    def processMessages(self):
        try:
            while True:
                messages = self.getMessageList()
                if messages.get('Messages'):
                    for message in messages.get('Messages'):
                        logging.debug(message)
                        messageBody = json.loads(message.get("Body"))
                        if self.validateMessage(message.get('MessageId'), message.get("ReceiptHandle")):
                            rentalDuration = self.calculateRentalDuration(messageBody.get('rentalId'), messageBody.get('returnTime'))
                            r = requests.post("{}/spaceinvaders".format(self.apiEndpointURL), headers={'Content-Type': 'application/json'}, data=json.dumps({'signature': messageBody.get('signature'), 'rentalDuration': rentalDuration, 'rentalId': messageBody.get('rentalId'), 'messageId': message.get('MessageId')}))
                            logging.info("Response Code from API Endpoint: {} with Message {}".format(r.status_code, r.text))
                            if self.rampageDecryption():
                                if r.status_code == 200:
                                    logging.info("Rental Successfully Processed: {}".format(message.get('MessageId')))
                                    self.removeMessage(message.get("ReceiptHandle"))
                                    msg = r.json()
                                    if int(msg.get('points')) < 0:
                                        logging.error(msg.get('message'))
                                else:
                                    logging.warning("There was an error processing message: {} Error Response: {}".format(message.get('MessageId'), r.text))

                else:
                    logging.info("There are no more messages to process")
        except ClientError as e:
            logging.critical("Error Processing Messages from SQS Queue: {}".format(e.response))

# ###############################################################
# This section below is to give Kyle his precious "Status Page".
# I mean, just because a red light isn't shining somewhere
# doesn't mean it's not working.
# Also, I won't forget how you complimented my Gagh on my 11th birthday!
# Biggest insult of my life.
# ##############################################################

app = Flask(__name__, template_folder='html')


@app.route('/')
def root():
    logging.info("Req: {}".format(request.url))
    resp = requests.get("http://169.254.169.254/latest/dynamic/instance-identity/document/")
    region = resp.json()['region']
    logging.info("You are running in {}".format(region))
    return render_template('index.html', region=region)
    # return app.send_static_file('index.html')


@app.route('/ping')
def status():
    logging.info("Req: {}".format(request.url))
    return "pong"


@app.route('/<path:file>', defaults={'file': 'index.html'})
def send_html(file):
    logging.info("Req: {}".format(request.url))
    return send_from_directory('html', file)


def startWebserver():
    logging.info("Starting Web Server")
    app.run(host='0.0.0.0', port=8088)

# #######################################################
# Now let's run this Bad Boy.
# #######################################################

if __name__ == '__main__':

    p2 = Process(target=startWebserver)
    p2.start()

    rental = Rental()
    p = Process(target=rental.processMessages())
    p.start()
    p.join()
