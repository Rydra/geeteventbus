# Melange

## An eventbus and AWS SNS+SQS messaging library for concurrent programming 

The spice must flow! (or in this case, the event)

Melange is offers a flexible library to create distributed event-driven architectures using 
Amazon Web Services SNS (Simple Notification Service) and SQS (Simple Queue Service) as message broker. 
Its main selling point is the capability to greatly decouple 
and integrate REST apis, AWS Lambda functions and console applications... as long as they can subscribe to SNS 
topics. (You can subscribe to SNS at the time of writing HTTP Post endpoints, 
AWS Lambdas, SQS Queues, emails and phones)

In addition, Melange supports event driven architectures in single-process, non-distributed, memory-based applications (Console applications, background workers)
with the aid of the `DomainEventBus` (see `Domain-Driven Design` section). The `DomainEventBus` is great if you really 
want to have a clean event-driven architecture with Domain Events, and its idea has been grabbed from Vaughn Vernon and his must-read book 
Implementing Domain-Driven Design (look at [part 3 of these series](http://dddcommunity.org/library/vernon_2011/) if you want a quick look,
 or read this excellent article from [Udi Dahan, founder of NServiceBus](http://udidahan.com/2009/06/14/domain-events-salvation/)).

Right now Melange only supports Amazon SNS+SQS as the backend messaging infrastructure, but in the 
future we want to expand this library to be flexible enough to be used with RabbitMQ as well.

## Installing ##

Execute the following two commands to install melange in your system (working in packaging this to combine both
commands into a single one):

```
pip install git+https://github.com/Rydra/redis-simple-cache.git/@master#egg=redis-simple-cache-0
pip install melange
```

## Preliminaries ##

For Melange to properly work you'll require an AWS account configured in your system 
(environment variables, .aws/credentials file...) and you must have SNS + SQS
permissions to create queues and topics, publish messages and perform subcriptions. 
I prefer to use environment variables. These are the AWS environment variables you would need if
you want to go with the environment variables route:

```
# Extracted from http://docs.aws.amazon.com/cli/latest/userguide/cli-environment.html

AWS_ACCESS_KEY_ID – AWS access key.
AWS_SECRET_ACCESS_KEY – AWS secret key. Access and secret key variables override credentials stored in credential and config files.
AWS_SESSION_TOKEN – Specify a session token if you are using temporary security credentials.
```

## How to get started ##

Event-driven architectures work with the Publish/Subscribe pattern to achieve decoupling.
So that publishers and subscribers do not know about each other. However in order to
communicate effectively a **Message Broker** is required to transfer messages from
publishers to subscribers. In Melange this message broker is **Amazon SNS**, which
will take messages from publishers and distribute those to all subscribers in a
fanout manner.

So, you will need two things to make this work: an **Exchange Message Publisher** and
an **Exchange Message Consumer** to send and receive messages respectively.

### Exchange Message Publisher ###

The simplest application that can work with Melange is creating a Publisher which will send messages:

```python
message_publisher = ExchangeMessagePublisher(topic='some-topic-name')

data = {
	'event_type_name': 'ProductAdded',
	'product_id': 12345,
	'name': 'Coolers'
}
message_publisher.publish(data)
# NOTE: You can as well call publish with `message_publisher.publish(data, event_type_name='ProductAdded')`
```

This piece of code will serialize the dictionary as JSON and send it to SNS to the topic `some-topic-name`.
If the topic does not exist, it will be created (though no one will receive the message...).
After that, all listeners subscribed to this topic will receive the message for
further processing (be an AWS Lambda, an email address, an Exchange Message Consumer, or any other
compatible Amazon SNS subscriber).

NOTE: The `event_type_name` property must exist in the dictionary. If it doesn't,
you must supply the event_type_name through the `event_type_name` parameter from
the publish method

### Exchange Message Consumer ###

After that, you may have in another separate project (be it a simple console application,
django worker, another thread, etc) an `Exchange Message Consumer` to receive these messages. And that consumer
will require, at least, one listener to be of any use.

The simplest implementation for that would be the following one, and you could place it in
the initialization of your application:


```python

class SampleListener(ExchangeListener):

	def process(self, event, **kwargs):
		print(f"I've received information about the product {event['name']}")
	
	def listens_to(self):
		return [ 'ProductAdded' ]

message_consumer = ExchangeMessageConsumer(event_queue_name='my-queue', topic_to_subscribe='some-topic-name')
message_consumer.subscribe(SampleListener())

while True:
	message_consumer.consume_event()
```

So, what's going on here? We've created a **Listener** that is interested in events of type
`ProductAdded` and will react to those events when received from the Message Broker. Override
`process` to provide behavior, and override `listens_to` to provide an array of event names you are
interested in.

We will attach this listener to a **queue**. A queue is a place where the messages received from
SNS will be stored and available for the consumer application at his own time. To do so, we first create
an `ExchangeMessageConsumer` with a queue name and a topic. If the queue does not exist, it will create
an **SQS queue** and subscribe it to the topic. 

Afterwards, you can subscribe an instance of your listener to the message consumer. Finally, you
create a loop that will poll for new events and invoke the `process` method of your ExchangeListener
for each event of the expected type it receives.

## Advanced usage

What you've seen so far is the simplest application of Melange to easily create a simple Publish/Subscribe
architecture. But you can go further than that and create a robust distributed application that fits
with other architecture patterns like **Hexagonal Architecture**, **Clean Architecture** or **CQRS**, properly
separating responsibilities.

### "Stronger" typing

In the examples provided above, you were passing plain dictionaries, and the framework, through the
`event_type_name` property could propertly distribute its message to the proper listeners. However
some people (myself included) sometimes prefer to work with objects instead of dictionaries if possible.
In that case you could declare your own `EventMessage` classes and use them with the publish/subscribe
methods. The example above would be rewritten like this with this approach:

Publisher:
```python
# In some file you would implement these classes
class ProductAddedSchema(EventSchema):
	""" This is a marshmallow schema! """
	product_id = fields.Int()
	name = fields.Str()
	
	@post_load
	def build(self, data):
		return ProductAdded(data['product_id'], data['name'], data['occurred_on'])

class ProductAdded(EventMessage):
	event_type_name = 'ProductAdded'
	
	def __init__(self, product_id, name, occurred_on=None):
		self.product_id = product_id
		self.name = name
		
# In you initialization code you would call the following line:
EventSerializer.instance().register(ProductAddedSchema)

message_publisher = ExchangeMessagePublisher(topic='some-topic-name')
message_publisher.publish(ProductAdded(product_id=12345, name='Coolers'))
```

Consumer:
```python
# In some file you would implement these classes
# Bear in mind that these definition are placed in
# another project, and you could define a different
# ProductAdded event (e.g. without the name property,
# maybe because you are not interested on that)
class ProductAddedSchema(EventSchema):
	""" This is a marshmallow schema! """
	product_id = fields.Int()
	name = fields.Str()
	
	@post_load
	def build(self, data):
		return ProductAdded(data['product_id'], data['name'], data['occurred_on'])

class ProductAdded(EventMessage):
	event_type_name = 'ProductAdded'
	
	def __init__(self, product_id, name, occurred_on=None):
		self.product_id = product_id
		self.name = name
		
class SampleListener(ExchangeListener):

	def process(self, event, **kwargs):
		# Note that I'm not accessing event properties by key, but as a regular object.
		# In fact event is of type ProductAdded, and this is possible thanks to marshmallow
		# post_load hook. If you don't add this hook, event would be again a dictionary
		print(f"I've received information about the product {event.name}")
	
	def listens_to(self):
		return [ 'ProductAdded' ]

# In you initialization code you would call the following line:
EventSerializer.instance().register(ProductAddedSchema)

message_consumer = ExchangeMessageConsumer(event_queue_name='my-queue', topic_to_subscribe='some-topic-name')
message_consumer.subscribe(SampleListener())
# You can subscribe as many listeners as you want

while True:
	message_consumer.consume_event()
```

Note the `Schema` classes. These are [marshmallow](https://marshmallow.readthedocs.io/en/latest/) schemas,
and they are used by the `EventSerializer` to serialize the `EventMessage` objects from/to JSON when publishing
or receiving messages. Then in your initialization code you must register the Schema in order to work with Melange.
The Schemas and their events are linked by naming convention, so a `ProductAdded` event will
need a `ProductAddedSchema` schema, a `UserRegistered` event will require a `UserRegisteredSchema` schema...
you get the idea.

Note as well the `occurred_on` property. It's a datetime fields that tells you when the event did
happen. This may be of use to you to guarantee correct ordering of message arrival on the Listeners.

It's a bit more complicated to implement, but the resulting code is cleaner and more readable
to another developer, and the intent, the event type and the property types for the event are clear 
and can be used as contract documentation for your listeners. Up to you and your needs/feelings.

### Threaded Exchange Message Consumer

The `ThreadedExchangeMessageConsumer` allows you to create a consumer that will poll the message queue
on a separate thread. The `ThreadedExchangeMessageConsumer` inherits from python `Thread` class, so
you can use them for your threading purposes.

The consumer example above would be rewritten like this:


```python

class SampleListener(ExchangeListener):

	def process(self, event, **kwargs):
		print(f"I've received information about the product {event['name']}")
	
	def listens_to(self):
		return [ 'ProductAdded' ]

message_consumer = ThreadedExchangeMessageConsumer(queue='my-queue', topic='some-topic-name')
message_consumer.subscribe(SampleListener())

message_consumer.start()

print('You can do other stuff from here, the consumer will poll events and call subscribers')
print('from a separate thread')
```

### Event Message de-duplication

Distributed architectures are hard, complex and come with a good deal of burdens, but they are required to achieve levels of scalability
and isolation harder to achieve on monolithic architectures. One of this issues is the possibility of
of the same message being received twice by the listeners. Network failures, application crashes, etc...
can cause this issue which, if not though or left undealt can cause your system to be out of sync and
run in an inconsistent state. This is why you need to take measures.

One of this measures is to, simply, write your listeners to be *idempotent*. This means that it does not
matter how many times a listener is called, the result will be the same and it won't impact or leave
the system into an inconsistent state.

However, sometimes writing idempotent code is just not possible. You require **message deduplication** to
account for this and ensure that a message won't be sent twice. You could use Amazon SQS FIFO Queues which
they say they provide this message deduplication, though not only FIFO queues are more expensive than
standard ones, [but exactly-once delivery is just impossible](https://dzone.com/articles/fifo-exactly-once-and-other-costs).
In Melange we have accounted for this with a *Redis cache* that will control that no message is delivered twice.

In order for this to work you have to provide the following environment variables as configuration
so that Melange can connect to your Redis database:

ENVIRONMENT VARIABLE NAME | Default | Description
--- | --- | ---
CACHE_REDIS_HOST | localhost| The host of your Redis
CACHE_REDIS_PORT | 6379 | The port of your Redis
CACHE_REDIS_DB | 0 | The DB to use for your Redis
CACHE_REDIS_PASSWORD | | The password of your Redis
CACHE_NAMESPACE | SimpleCache | You can provide a namespace so that values created by Melange do not collide with each other

If Melange is unable to connect to your Redis it will function normally but you won't enjoy the
benefits of ensuring message deduplication, which may lead your distributed application in an inconsitent
state. You're warned :).

### Domain-Driven Design

In his book "Implementing Domain-Driven Design", in Chapter 8 when talking about Domain Events describes
an implementation of a `Domain Event Publisher`. Domain Events are part of the ubiquitous language and
part of your Domain, and your domain should be abstracted from implementation details like your messaging
framework. This is why I decided to integrate here a `DomainEventBus`.

The `DomainEventBus` is intended to be used inside your Domain Model as the mecanism to publish
Domain Events and forward them to interested parties. DO NOT confuse this concept of Bus with 
Publish/Subscribe to a Message Broker like RabbitMQ or Amazon SNS+SQS. This bus lives in the same
thread as the entity or domain service that implements your Domain Model.

An example of use:

```python
class MySubscriber(DomainSubscriber):
	def process(self, event):
		print (f"{event.product_id}{event.name}")
		
	def listens_to(self):
		return [ ProductAddedDomainEvent ]
		

DomainEventBus.instance().reset() # Remember to always reset the bus prior to usage in the current thread

DomainEventBus.instance().subscribe(MySubscriber())

# ... inside your business logic at some point ...

product_repository.add(my_product)
DomainEventBus.instance().publish(ProductAddedDomainEvent(my_product.id, my_product.name))
```

If you wanna learn more about how to do clean architectures and domain well isolated from
your technology stack I advise, again, to read *Implementing Domain-Driven Design* from Vaughn Vernon
and *Clean Architecture* from Uncle Bob

# Other useful uses

### AWS Lambda functions

Melange is great to communicate with AWS Lambda functions and integrate them with other lambdas or systems. 
You could:

- Use the `MessagePublisher` to publish events to SNS topics (which then could trigger other Lambdas/systems).
- Use the `MessageConsumer` on a schedule-job based lambda to dequeue one event from an SQS queue for processing.

If the Lambda is triggered by SNS, SNS will wrap the message in a dictionary structure. You can deserialize the 
message by using the `parse_event_from_sns` function.

Example of a Lambda function code:

```python
def handle_event(message, context):

	EventSerializer.instance().register(MyEventSchema, MyFooCreatedSchema)

    event = parse_event_from_sns(message)

	# Here you can check whether the parsed event is the one expected by your Lambda function
    if not isinstance(event, MyEvent):
        raise Exception('The passed event is not a MyEvent')

	# Your event-processing code here...
	do_work(event)
	
	message_publisher = MessagePublisher(topic='some-topic')
	
	# This publish, depending on who is suscribed to the topic, will trigger other systems.
	event_to_publish = MyFooCreated()
	message_publisher.publish(event_to_publish)
```

### Interact with Django/Flask APIs
 
SNS allows you to register endpoints on topics. You can use the `MessagePublisher` to publish messages to these 
SNS topics and SNS will send the messages to those endpoints, allowing you to seamlessly integrate your apis and 
other systems.


# Why the name 'Melange'

The name "Melange" is a reference to the drug-spice from the sci-fi book saga "Dune", a spice which is only 
generated in a single planet in the universe (planet Dune) and every human depends on it.

>If the spice flows, then the spice can be controlled.  
He who controls the spice, controls the universe.  
The spice must flow.

The analogy can be very well made on Events in a distributed architecture :)
