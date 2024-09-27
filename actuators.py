import RPi.GPIO as GPIO
import time

COLOR_PINS = {
    "green" : 27,
    "red" : 17
}

COLOR_TOGGLE_STATES = {
    "on" : GPIO.LOW,
    "off" : GPIO.HIGH
}

def color_toggle(color, on_off):
    pin = COLOR_PINS[color] 
    col_out = COLOR_TOGGLE_STATES[on_off]

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(pin,GPIO.OUT)
    GPIO.output(pin,col_out)

    GPIO.cleanup()


def gate_angle(angle):
    
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(22, GPIO.OUT)

    pwm=GPIO.PWM(22, 50)
    pwm.start(0)

    def setAngle(angle):
        duty = angle / 18 + 2
        GPIO.output(22, True)
        pwm.ChangeDutyCycle(duty)
        GPIO.output(22, False)
        pwm.ChangeDutyCycle(duty)


    setAngle(angle)

    pwm.stop()
    GPIO.cleanup()

def gate_open():
    gate_angle(20)

def gate_close():
    gate_angle(170)