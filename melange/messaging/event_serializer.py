import json

from marshmallow import ValidationError
from singleton import Singleton

from .event_message import EventMessage


class EventSerializer(metaclass=Singleton):
    def __init__(self):
        self.event_serializer_map = {}

    def register(self, *serializers):
        for serializer in serializers:
            self.event_serializer_map[serializer.__qualname__] = serializer()

    def deserialize(self, event_dict):
        try:
            event_schema = event_dict['event_type_name'] + 'Schema'

            if event_schema not in self.event_serializer_map:
                raise ValueError("The event type {} doesn't have a registered serializer".format(event_dict['event_type_name']))

            schema = self.event_serializer_map[event_schema]

            try:
                data = schema.load(event_dict)
                return data
            except ValidationError:
                return event_dict
        except (ValueError, KeyError):
            return event_dict

    def serialize(self, event):
        if isinstance(event, EventMessage):
            event_schema = event.event_type_name + 'Schema'

            if event_schema not in self.event_serializer_map:
                raise ValueError("The event type {} doesn't have a registered serializer".format(event.event_type_name))

            schema = self.event_serializer_map[event_schema]
            data = schema.dumps(event)
            return data
        else:
            return json.dumps(event)
