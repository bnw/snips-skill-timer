#!/usr/bin/env python3

from hermes_python.hermes import Hermes, MqttOptions
from datetime import timedelta
import time
from threading import Thread
import toml
from subprocess import call


USERNAME_INTENTS = "mcitar"
MQTT_BROKER_ADDRESS = "localhost:1883"
MQTT_USERNAME = None
MQTT_PASSWORD = None

TIMER_LIST = []

class TimerBase(Thread):
    """
    """
    def __init__(self, hermes, intentMessage):

        super(TimerBase, self).__init__()

        self._start_time = 0

        self.hermes = hermes
        self.session_id = intentMessage.session_id
        self.site_id = intentMessage.site_id
        self.sentence = None
        self.timerType = u"Teimer"


        if intentMessage.slots.duration:
            duration = intentMessage.slots.duration.first()
            self.durationRaw = self.get_duration_raw(duration)

            self.wait_seconds = self.get_seconds_from_duration(duration)
        else:
            text_now = u"Ich habe die Dauer des Teimers nicht verstanden, sorry"
            hermes.publish_end_session(intentMessage.session_id, text_now)
            raise Exception('Timer need dutration')


        if intentMessage.slots.timer_type:
            timer = str(intentMessage.slots.timer_type.first().value)
            if timer == "Timer":
                self.timerType = "Teimer"
            else:
                self.timerType = u"{} Teimer".format(timer)


        #if intentMessage.slots.sentence: .... dont know why this is not working...
        #    self.sentence = intentMessage.slots.sentence.first().rawValue
        #else:
        #    self.sentence = None

        TIMER_LIST.append(self)

        self.send_end()

    @staticmethod
    def get_seconds_from_duration(duration):

        days = duration.days
        hours = duration.hours
        minutes = duration.minutes
        seconds = duration.seconds
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds).total_seconds()

    @staticmethod
    def get_duration_raw(duration):

        result = ''

        days = duration.days
        hours = duration.hours
        minutes = duration.minutes
        seconds = duration.seconds

        length = 0

        if seconds > 0:
            result = '{} Sekunde'.format(str(seconds))
            length += 1
        if minutes > 0:
            if length > 0:
                add_and = ' und '
            else:
                add_and = ''
            result = '{} Minuten{}{}'.format(str(minutes), add_and, result)
            length += 1
        if hours > 0:
            if length > 1:
                add_and = ', '
            elif length > 0:
                add_and = ' und '
            else:
                add_and = ''
            result = '{} Stunden{}{}'.format(str(hours), add_and, result)
            length += 1
        if days > 0:
            if length > 1:
                add_and = ', '
            elif length > 0:
                add_and = ' und '
            else:
                add_and = ''
            result = '{} Tagen{}{}'.format(str(days), add_and, result)
        return result

    @property
    def remaining_time(self):
        if self._start_time == 0:
            return 0
        return int((self._start_time + self.wait_seconds) - time.time())

    @property
    def remaining_time_str(self):
        seconds = self.remaining_time

        if seconds == 0:
            return None

        result = ''
        add_and = ''
        t = str(timedelta(seconds=seconds)).split(':')

        if int(t[2]) > 0:
            add_and = ' und '
            result += "{} Sekunden".format(int(t[2]))

        if int(t[1]) > 0:
            result = "{} Minuten {}{}".format(int(t[1]), add_and, result)
            if add_and != '':
                add_and = ', '
            else:
                add_and = ' et '

        if int(t[0]) > 0:

            result = "{} Stunden{}{}".format(int(t[0]), add_and, result)
        return result

    def run(self):

        print("[{}] Start teimer: wait {} seconds".format(time.time(), self.wait_seconds))
        self._start_time = time.time()
        time.sleep(self.wait_seconds)
        self.__callback()

    def __callback(self):
        print("[{}] End timer: wait {} seconds".format(time.time(), self.wait_seconds))
        TIMER_LIST.remove(self)
        self.callback()

    def callback(self):
        raise NotImplementedError('You should implement your callback')

    def send_end(self):
        raise NotImplementedError('You should implement your send end')


class TimerSendNotification(TimerBase):

    def callback(self):
        if self.sentence is None:
            text = u"Dein {} {} ist abgelaufen".format(str(self.durationRaw), str(self.timerType))
        else:
            text = u"Dein {} {} ist abgelaufen{}".format(
                self.durationRaw, self.timerType, self.sentence)

        call(["aplay", "-q", "Gentle-wake-alarm-clock.wav"])

        self.hermes.publish_start_session_notification(site_id=self.site_id, session_initiation_text=text,
                                                       custom_data=None)

    def send_end(self):
        if self.sentence is None:
            text_now = u"{} {} ab jetzt".format(str(self.durationRaw),str(self.timerType))
        else:
            text_now = u" {} {}  {} ab jetzt".format(str(self.durationRaw), str(self.timerType), str(self.sentence))

        self.hermes.publish_end_session(self.session_id, text_now)


class TimerSendAction(TimerBase):

    def callback(self):
        self.hermes.publish_start_session_action(site_id=self.site_id, session_init_text=self.sentence,
                                                 session_init_intent_filter=[],
                                                 session_init_can_be_enqueued=False, custom_data=None)

    def send_end(self):
        if self.sentence is None:
            raise Exception('TimerSendAction need sentence with action')
        text_now = u"In {} werde ich folgendes tun: {}".format(str(self.durationRaw), str(self.sentence))
        self.hermes.publish_end_session(self.session_id, text_now)


def timerRemember(hermes, intentMessage):
    timer = TimerSendNotification(hermes, intentMessage)
    timer.start()


def timerAction(hermes, intentMessage):
    # Example in 15 minutes start the TV
    timer = TimerSendAction(hermes, intentMessage)
    timer.start()


def timerRemainingTime(hermes, intentMessage):
    len_timer_list = len(TIMER_LIST)
    text = "Du hast {} Teimer. ".format(str(len_timer_list))
    if len_timer_list < 1:
        hermes.publish_end_session(intentMessage.session_id, "Es läuft kein Teimer")
    else:
        for i, timer in enumerate(TIMER_LIST):
            text += u" auf dein {} Teimer sind noch {} übrig. ".format(getFirstSecondTimer(i + 1), timer.remaining_time_str)
            if len_timer_list <= i:
                text += u", "
        hermes.publish_end_session(intentMessage.session_id, text)


def getFirstSecondTimer(i):
    switcher={
            1:'erste',
            2:'zweite',
            3:'dritte',
            4:'viere',
            5:'fünfte',
         }
    return switcher.get(i,"weiter")


def timerRemove(hermes, intentMessage):
    TIMER_LIST.clear()
    text = u'Alle Teimer gelöscht'
    hermes.publish_end_session(intentMessage.session_id, text)


def timerList(hermes, intentMessage):
    timer.end()


if __name__ == "__main__":
    snips_config = toml.load('/etc/snips.toml')
    if 'mqtt' in snips_config['snips-common'].keys():
        MQTT_BROKER_ADDRESS = snips_config['snips-common']['mqtt']
    if 'mqtt_username' in snips_config['snips-common'].keys():
        MQTT_USERNAME = snips_config['snips-common']['mqtt_username']
    if 'mqtt_password' in snips_config['snips-common'].keys():
        MQTT_PASSWORD = snips_config['snips-common']['mqtt_password']

    mqtt_opts = MqttOptions(username=MQTT_USERNAME, password=MQTT_PASSWORD, broker_address=MQTT_BROKER_ADDRESS)
    with Hermes(mqtt_options=mqtt_opts) as h:
        h.subscribe_intent("mcitar:timerRemember", timerRemember)
        h.subscribe_intent("mcitar:timerRemainingTime", timerRemainingTime)
        h.subscribe_intent("mcitar:timerRemove", timerRemove)
        h.loop_forever()
