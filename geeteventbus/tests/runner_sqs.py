'''Tests for eventbus operations '''

import logging
import sys
import unittest
from signal import signal, SIGTERM, SIGINT
from threading import Lock
from time import sleep

from geeteventbus.event import Event
from geeteventbus.eventbus_factory import EventBusFactory
from geeteventbus.sqs_eventbus import SQSEventBus
from geeteventbus.subscriber import subscriber

ebus = None


class event_mine(Event):
    event_type_name = 'event_mine'

    def __init__(self, topic, data, ident, ordered=None, event_type_name='event_mine'):
        Event.__init__(self, topic, event_type_name, ordered)
        self.data = data
        self.id = ident

    def set_status(self, status):
        self.data['status'] = status

    def get_status(self):
        return self.data['status']

    def set_id(self, ident):
        self.id = ident

    def get_id(self):
        return self.id


class subuscriber_mine(subscriber):
    def __init__(self):
        print('Test subscriber initialized')
        self.processed_events = []
        self.lock = Lock()

    def process(self, event):
        event.set_status('processed')
        with self.lock:
            self.processed_events.append(event)

    def get_processed_events(self):
        with self.lock:
            ret = self.processed_events[:]
            return ret


class test_runner(unittest.TestCase):
    def setUp(self):
        print('Setting up')
        self.topic = 'topic'
        self.events = []
        self.ordered_events = []
        self.ebus = None
        i = 0
        while i < 25:
            self.ordered_events.append(event_mine(self.topic, {'status': 'notprocessed'}, i, 'ord'))
            i += 1
        i = 0
        while i < 25:
            self.events.append(event_mine(self.topic, {'status': 'notprocessed'}, i))
            i += 1
        self.subscriber = subuscriber_mine()

    def tearDown(self):
        self.ebus.shutdown()
        self.ebus = None
        self.events = None
        self.ordered_events = None
        self.subscriber = None

    def alltests(self):
        self.ebus.register_consumer(self.subscriber, self.topic, event_mine)
        for ev in self.events:
            self.ebus.post(ev)
        for ev in self.ordered_events:
            self.ebus.post(ev)
        sleep(2)
        nextexpectid = 0
        processed_events = self.subscriber.get_processed_events()
        for ev in processed_events:
            if ev.get_status() != 'processed':
                return False
            if ev.get_ordered() is not None:
                ident = ev.get_id()
                if ident != nextexpectid:
                    return False
                nextexpectid += 1
        return True

    def test_sqs_eventbus(self):
        global ebus
        self.ebus = SQSEventBus()
        ebus = self.ebus
        self.assertTrue(self.alltests())


def interuppt_handler(signo, statck):
    if ebus is not None:
        try:
            ebus.shutdown()
        except Exception as e:
            logging.error(e)
            pass
        sys.exit(1)


if __name__ == '__main__':
    signal(SIGTERM, interuppt_handler)
    signal(SIGINT, interuppt_handler)
    unittest.main()
    sleep(2)
