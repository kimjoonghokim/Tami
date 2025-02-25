#initialize buzzer and LEDs
from gpiozero import Buzzer, LED
buzzer = Buzzer(21)
red = LED(14)
green = LED(15)

# import the necessary packages
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import img_to_array
from tensorflow.keras.models import load_model
from imutils.video import VideoStream
from imutils.video.pivideostream import PiVideoStream
import numpy as np
import argparse
import imutils
import time
import cv2
import os
import pygame
import RPi.GPIO as GPIO
import adafruit_amg88xx
import busio
import board
import functools
import operator

i2c_bus = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_amg88xx.AMG88XX(i2c_bus)
FEVERTEMP = 38; #38 is the typical fever temperature, feel free to change
os.putenv('SDL_FBDEV', '/dev/fb1')
pygame.init()
screen = pygame.display.set_mode((1080,1920))
screen.fill((255,255,255))

greenArrow = pygame.image.load("greenarrow.png")
greenArrow = pygame.transform.scale(greenArrow,(700,700))

redX = pygame.image.load("redx.png")
redX = pygame.transform.scale(redX,(700,700))

greenCheck = pygame.image.load("greencheck.png")
greenCheck = pygame.transform.scale(greenCheck,(900,700))

statusSymbol = greenArrow

font = pygame.font.SysFont("Arial", 60)
black = (0,0,0)
feverDetected = font.render("Fever Detected! Please Exit", True, black)
maskDetected = font.render("Mask detected, You May Enter", True, black)
maskNotDetected = font.render("Please put on your mask!", True, black)
approachTami = font.render("     Please come closer", True, black)

statusText = approachTami

pygame.display.update()

def detect_and_predict_mask(frame, faceNet, maskNet):
    # grab the dimensions of the frame and then construct a blob
    # from it
    (h, w) = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
        (104.0, 177.0, 123.0))

    # pass the blob through the network and obtain the face detections
    faceNet.setInput(blob)
    detections = faceNet.forward()

    # initialize our list of faces, their corresponding locations,
    # and the list of predictions from our face mask network
    faces = []
    locs = []
    preds = []

    # loop over the detections
    for i in range(0, detections.shape[2]):
        # extract the confidence (i.e., probability) associated with
        # the detection
        confidence = detections[0, 0, i, 2]

        # filter out weak detections by ensuring the confidence is
        # greater than the minimum confidence
        if confidence > args["confidence"]:
            # compute the (x, y)-coordinates of the bounding box for
            # the object
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")

            # ensure the bounding boxes fall within the dimensions of
            # the frame
            (startX, startY) = (max(0, startX), max(0, startY))
            (endX, endY) = (min(w - 1, endX), min(h - 1, endY))

            # extract the face ROI, convert it from BGR to RGB channel
            # ordering, resize it to 224x224, and preprocess it
            face = frame[startY:endY, startX:endX]
            face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
            face = cv2.resize(face, (224, 224))
            face = img_to_array(face)
            face = preprocess_input(face)

            # add the face and bounding boxes to their respective
            # lists
            faces.append(face)
            locs.append((startX, startY, endX, endY))

    # only make a predictions if at least one face was detected
    if len(faces) > 0:
        # for faster inference we'll make batch predictions on *all*
        # faces at the same time rather than one-by-one predictions
        # in the above `for` loop
        faces = np.array(faces, dtype="float32")
        preds = maskNet.predict(faces, batch_size=32)
        
    else:
        statusSymbol = greenArrow

    # return a 2-tuple of the face locations and their corresponding
    # locations
    return (locs, preds)

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-f", "--face", type=str,
    default="face_detector",
    help="path to face detector model directory")
ap.add_argument("-m", "--model", type=str,
    default="mask_detector.model",
    help="path to trained face mask detector model")
ap.add_argument("-c", "--confidence", type=float, default=0.5,
    help="minimum probability to filter weak detections")
args = vars(ap.parse_args())

# load our serialized face detector model from disk
print("[INFO] loading face detector model...")
prototxtPath = os.path.sep.join([args["face"], "deploy.prototxt"])
weightsPath = os.path.sep.join([args["face"],
    "res10_300x300_ssd_iter_140000.caffemodel"])
faceNet = cv2.dnn.readNet(prototxtPath, weightsPath)

# load the face mask detector model from disk
print("[INFO] loading face mask detector model...")
maskNet = load_model(args["model"])

# initialize the video stream and allow the camera sensor to warm up
print("[INFO] starting video stream...")
#vs = VideoStream(src=0).start()
#vs = VideoStream(usePiCamera=True).start()
vs = PiVideoStream().start()

time.sleep(2.0)

# loop over the frames from the video stream
while True:
    # grab the frame from the threaded video stream and resize it
    # to have a maximum width of 400 pixels
    frame = vs.read()
    frame = imutils.resize(frame, width=500)
    
    start = time.time()
    # detect faces in the frame and determine if they are wearing a
    # face mask or not
    (locs, preds) = detect_and_predict_mask(frame, faceNet, maskNet)
    screen.fill((255,255,255))
    screen.blit(statusSymbol,(190,1000))
    screen.blit(statusText,(190, 800))
    pygame.display.update()
    flatList = functools.reduce(operator.iconcat, sensor.pixels, [])   #Create a flatlist of the temperatures
    j = flatList
    # loop over the detected face locations and their corresponding
    # locations
    for (box, pred) in zip(locs, preds):
        # unpack the bounding box and predictions
        (startX, startY, endX, endY) = box
        (mask, withoutMask) = pred

        # determine the class label and color we'll use to draw
        # the bounding box and text
        if mask > withoutMask:
            label = "Face Mask Detected"
            color = (0, 255, 0)
            prevSymbol = statusSymbol
            statusSymbol = greenCheck
            statusText = maskDetected
            statusTime = time.time()
            if(sum(i>FEVERTEMP for i in j) >1):
                statusText = feverDetected
                statusSymbol = redX
                
            pygame.display.update()
            buzzer.off()
            
        if mask< withoutMask:
            label = "No Face Mask Detected"
            prevSymbol = statusSymbol
            statusSymbol = redX
            statusText = maskNotDetected
            statusTime = time.time()
            color = (0, 0, 255)
            if(sum(i>FEVERTEMP for i in j) >1):
                statusText = feverDetected
                statusSymbol = redX
            pygame.display.update()
            buzzer.on()
       
            
            
        # display the label and bounding box rectangle on the output
        # frame
        cv2.putText(frame, label, (startX-50, startY - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)

    # show the output frame
    cv2.namedWindow("Face Mask Detector")
    cv2.moveWindow("Face Mask Detector", 290,250)
    cv2.imshow("Face Mask Detector", frame)
    key = cv2.waitKey(1) & 0xFF
    end = time.time()
    t = end - start
    fps = 1/t
    print(fps)
    # if the `q` key was pressed, break from the loop
    if key == ord("q"):
        break

# do a bit of cleanup
cv2.destroyAllWindows()
vs.stop()

