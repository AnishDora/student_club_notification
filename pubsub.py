

# -*- coding: utf-8 -*-
"""
==============================================================================
Name:    pubsub
Purpose: Simple publish & subscribe pattern in pure python (object designed).
         Messages can be posted by one ore more publishers on channels and
         subscribers can get those messages.
         Can be used in a threaded project to communicate asynchronously
         between light-weight process running in different threads.
Reference:    https://en.wikipedia.org/wiki/Publish–subscribe_pattern
Requirement:  Python >= 3.6, [pytest, pylint, flake8, coverage]
==============================================================================
"""

import warnings
from threading import Lock
from queue import Queue, PriorityQueue, Empty


class PubSubBase():
    """
    PubSubBase should not be used,
    Please use classes PubSub and PubSubPriority
    The algorithms for thread safe functionnalities were designed
    by Zhen Wang : congratulation to him !
    This class is based on thread-safe FIFO queue Python
    implementation and was designed thread-safe by Zhen Wang.
    """

    def __init__(self, max_queue_in_a_channel=100, max_id_4_a_channel=2**31):
        """
        Create an object to be used as a communicator in a project
        between publishers and subscribers
        Optionals parameters :
        - max_queue_in_a_channel : (be careful, modify if necessary)
            - Maximum number of message in a channel.
            - Default value: 100
            - If you intend to send a lot of message in a channel,
              Please increase this parameters value to suit you,
              else the channel is going to overflow and
              listener will receive None and the channel will be
              closed.
        - max_id_4_a_channel : (don't modify)
            - Maximum value for message 'id' field value on a
              communication channel.
              Used to prevent negative message ids
              to appear when number of messages broadcasted by
              this channel is very big.
            - Default value: 2**31
        """

        self.max_queue_in_a_channel = max_queue_in_a_channel
        self.max_id_4_a_channel = max_id_4_a_channel

        self.channels = {}
        self.count = {}

        self.channels_lock = Lock()
        self.count_lock = Lock()

    def subscribe_(self, channel, is_priority_queue):
        """
        Return a synchronised FIFO queue object used by a subscriber
        to listen at messages sent by publishers on a given channel.
        No problem if channel doesn't exists yet.
        Ref.: https://docs.python.org/3/library/queue.html
        Parameters:
        - channel : the channel to listen to.
        - is_priority_queue : True if FIFO queue give message according
                            their priority else FIFO queue without
                            priority.
        """

        if not channel:
            raise ValueError('channel : None value not allowed')

        if channel not in self.channels:
            self.channels_lock.acquire()
            # Need to check again
            if channel not in self.channels:
                self.channels[channel] = []
            self.channels_lock.release()

        message_queue = None
        if is_priority_queue:
            message_queue = ChanelPriorityQueue(self, channel)
        else:
            message_queue = ChanelQueue(self, channel)
        self.channels[channel].append(message_queue)

        return message_queue

    def unsubscribe(self, channel, message_queue):
        """
        Used by a subscriber who doesn't want to receive messages
        on a given channel and on a queue (message_queue)
        obtained previously by subscribe method.
        """
        if not channel:
            raise ValueError('channel : None value not allowed')
        if not message_queue:
            raise ValueError('message_queue : None value not allowed')
        if channel in self.channels:
            self.channels[channel].remove(message_queue)

    def publish_(self, channel, message, is_priority_queue, priority):
        """
        Called by publisher.
        Send a message in a channel, all subscribers registered on this
        communication channel are going to receive the message.
        If the channel doesn't exists, it is created.
        If Nobody listen to the channel (like often in real life) :
        no matter...
        If channel overflows, ie the actual message number in channel
        is bigger than max_queue_in_a_channel parameter value,
        send a warning and ignore message.
        Queue can be used later when it is not full.
        Parameters :
            - channel : a string identifying the channel
            - message : payload that will be carried by the message.
            - is_priority_queue : True if FIFO queue give message according
                                their priority else FIFO queue without
                                priority.
            - priority lowest = first send to listeners :
                    - Integer for importance of this message.
                    - Default value: 100
                    - 0 is the higther priority
        Message received by subscribers using listen() method is a
        python dictionary with 2 keys registered inside, see listen()
        method documentation for more.
        """

        if priority < 0:
            raise ValueError('priority must be > 0')
        if not channel:
            raise ValueError('channel : None value not allowed')
        if not message:
            raise ValueError('message : None value not allowed')

        if channel not in self.channels:
            self.channels_lock.acquire()
            # Need to check again
            if channel not in self.channels:
                self.channels[channel] = []
            self.channels_lock.release()

        # Update message self.counts
        self.count_lock.acquire()
        if channel not in self.count:
            self.count[channel] = 0
        else:
            self.count[channel] = ((self.count[channel] + 1) %
                                   self.max_id_4_a_channel)
        self.count_lock.release()

        # ID of current message
        _id = self.count[channel]

        # Push message to all subscribers in channel
        for channel_queue in self.channels[channel]:
            # Check if queue overflowed
            if channel_queue.qsize() >= self.max_queue_in_a_channel:
                warnings.warn((
                    f"Queue overflow for channel {channel}, "
                    f"> {self.max_queue_in_a_channel} "
                    "(self.max_queue_in_a_channel parameter)"))
            else:  # No overflow on this channel_queue
                # Build and send message for this queue
                if is_priority_queue:
                    # OrderedDict dictionnary for sorting message
                    # on their id if they have the same priority.
                    channel_queue.put((priority,
                                       OrderedDict(data=message, id=_id)),
                                      block=False)
                else:
                    channel_queue.put({'data': message, 'id': _id},
                                      block=False)


class ChanelQueue(Queue):
    """
    A FIFO queue for a channel.
    """

    def __init__(self, parent, channel):
        """
        Create a new queue for the channel
        Parameters :
        - parent : communicator parent
        - channel : string for the name of the channel
        """
        super().__init__()
        self.parent = parent
        self.name = channel

    def listen(self, block=True, timeout=None):
        """
        Called by a subscriber when he wants to get messages from
        a channel.
        This is an iterator that can be used to get messages sent by a
        publisher in the queue.
        Iterator can be casted in Python list to get all messages in it
        with : msgs = list(messageQueue.listen(block=False))
        Messages returned are of type dictionary with 2 keys registered by
        by publish() method:
            'data' : the message's payload that was put in the queue by
                        publishers (see publish() method).
            'id' : Number of this message on the current channel
        Parameters :
        - block (default value: True) and timeout (default value: None)
            and behaviours if no message is in the queue.
            Documentation can be found in
            Python official Queue documentation and especially in its get()
            method : see https://docs.python.org/3/library/queue.html
        - timeout : None : no timeout or positive integer see
            Python official Queue documentation and especially in its get()
            method : see https://docs.python.org/3/library/queue.html
        """

        while True:
            try:
                data = self.get(block=block, timeout=0)
                assert isinstance(data, dict) and len(data) == 2,\
                       "Bad data in chanel queue !"
                yield data
            except Empty:
                return

    def unsubscribe(self):
        """
        Used by a subscriber who doesn't want to receive messages
        on a given this channel and on a this queue
        """
        self.parent.unsubscribe(self.name, self)


class ChanelPriorityQueue(PriorityQueue):
    """
    A FIFO priority queue for a channel.
    """

    def __init__(self, parent, channel):
        """
        See : ChanelQueue.__init__() method
        """
        super().__init__()
        self.parent = parent
        self.name = channel

    def listen(self, block=True, timeout=None):
        """
        See : ChanelQueue.listen() method
        """

        while True:
            try:
                priority_data = self.get(block=block, timeout=0)
                assert isinstance(priority_data, tuple) and \
                       len(priority_data) == 2 and \
                       isinstance(priority_data[1], dict) and \
                       len(priority_data[1]) == 2, "Bad data in chanel queue !"
                yield priority_data[1]
            except Empty:
                return

    def unsubscribe(self):
        """
        Used by a subscriber who doesn't want to receive messages
        on a given this channel and on a this queue
        """
        self.parent.unsubscribe(self.name, self)


class PubSub(PubSubBase):
    """
    Implement communication Design Pattern : Publish-subscribe
    Ref : https://en.wikipedia.org/wiki/Publish–subscribe_pattern
    Publishers write messages on channels and subscribers get them
    in an asynchronous way.
    For limitations, see  PubSubBase.__init__() constructor
    parameters and default values.
    This class is based on thread-safe FIFO queue standard Python
    implementation and was designed thread-safe by Zhen Wang.
    """

    def subscribe(self, channel):
        """
        Return a synchronised normal FIFO queue object
        used by a subscriber to listen at messages sent
        by publishers on a given channel.
        No problem if channel doesn't exists yet.
        See  PubSubBase.subscribe() for more details
        Parameter:
        - channel : the channel to listen to.
        """
        return self.subscribe_(channel, False)

    def publish(self, channel, message):
        """
        See  PubSubBase.publish() for more details
        """
        self.publish_(channel, message, False, priority=100)


class PubSubPriority(PubSubBase):
    """
    Same as PubSub class but deal with messages priorities.
    Send registred messages in priority order (lowest first)
    For limitations, see  PubSub __init__() constructor parameters and
    default values.
    This class is based on thread-safe FIFO PriorityQueue Python
    implementation.
    """

    def subscribe(self, channel):
        """
        Return a synchronised FIFO priority queue object
        used by a subscriber to listen at messages sent
        by publishers on a given channel.
        No problem if channel doesn't exists yet.
        See  PubSubBase.subscribe_() for more details
        Parameter:
        - channel : the channel to listen to.
        """

        return self.subscribe_(channel, True)

    def publish(self, channel, message, priority=100):
        """
        See PubSubBase.publish() for more details
        """
        self.publish_(channel, message, True, priority)


class OrderedDict(dict):
    """
    A dictionary sub-class that implements < operator
    that use the id field to order messages with
    the same priority
    """

    def __lt__(self, other):
        """
        For sorting messages with same priority from oldest to newest
        Return True if this element id is lower than other element
        given in parameter.
        """
        return self['id'] < other['id']
