'''Tests for eventbus operations '''

import logging
import sys
import unittest
from signal import signal, SIGTERM, SIGINT
from time import sleep

from melange.aws.message_consumer import ExchangeMessageConsumer

from melange.aws.event_serializer import EventSerializer
from melange.aws.eventbus import EventBus
from melange.aws.threaded_message_consumer import ThreadedExchangeMessageConsumer
from melange.event import Event, EventSchema
from marshmallow import fields, post_load

from melange.exchangelistener import ExchangeListener

ebus = None

NUM_EVENTS_TO_PUBLISH = 1

class EventMineSchema(EventSchema):
    data = fields.Dict()
    id = fields.Integer()

    @post_load
    def create_event_mine(self, data):
        return EventMine(data['data'], data['id'])


class EventMine(Event):
    event_type_name = 'EventMine'

    def __init__(self, data, id):
        Event.__init__(self, self.event_type_name)
        self.data = data
        self.id = id

    def set_status(self, status):
        self.data['status'] = status

    def get_status(self):
        return self.data['status']

    def get_id(self):
        return self.id


class SubscriberMine(ExchangeListener):
    def __init__(self):
        super().__init__('dev-test-topic')
        print('Test subscriber initialized')
        self.processed_events = []

    def process(self, event, **kwargs):
        event.set_status('processed')
        self.processed_events.append(event)

    def listens_to(self):
        return EventMine.event_type_name

    def get_processed_events(self):
        return self.processed_events[:]


class TestRunner(unittest.TestCase):
    def setUp(self):
        print('Setting up')
        self.topic = 'dev-test-topic'
        self.events = [EventMine({'status': 'notprocessed'}, i) for i in range(NUM_EVENTS_TO_PUBLISH)]
        EventSerializer.instance().register(EventMineSchema, EventMineSchema)
        self.message_consumer = ThreadedExchangeMessageConsumer(
            event_queue_name='dev-test-queue',
            topic_to_subscribe=self.topic)

        self.message_consumer.start()

        self.subscriber = SubscriberMine()

    def tearDown(self):
        self.message_consumer.shutdown()
        self.events = None
        self.ordered_events = None
        self.subscriber = None

    def alltests(self):
        self.message_consumer.subscribe(self.subscriber)
        for ev in self.events:
            EventBus.get_instance().publish(ev)

        sleep(3)

        processed_events = self.subscriber.get_processed_events()

        return len(processed_events) == NUM_EVENTS_TO_PUBLISH and all(ev.get_status() == 'processed' for ev in processed_events)

    def test_sqs_eventbus(self):
        success = self.alltests()
        self.assertTrue(success)


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
