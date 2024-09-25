#Example Servo Code
#Control the angle of a
#Servo Motor with Raspberry Pi

# free for use without warranty
# www.learnrobotics.org

import RPi.GPIO as GPIO
from time import sleep


import sys

ctrl = int(sys.argv[1])

GPIO.setmode(GPIO.BOARD)
GPIO.setup(22, GPIO.OUT)

pwm=GPIO.PWM(22, 50)
pwm.start(0)

def setAngle(angle):
    duty = angle / 18 + 2
    GPIO.output(22, True)
    pwm.ChangeDutyCycle(duty)
    sleep(1)
    GPIO.output(22, False)
    pwm.ChangeDutyCycle(duty)

count = 0
numLoops = 1

while count < numLoops:
#    print("set to 0-deg")
#    setAngle(0)
#    sleep(1)


    print("set to 135-deg")
    setAngle(ctrl)
    sleep(1)

#    setAngle(0)

    count=count+1

pwm.stop()
GPIO.cleanup()
