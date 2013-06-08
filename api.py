from google.appengine.api import users
from google.appengine.api import channel
from google.appengine.api import memcache
import model
import webapp2
import json
import logging
import datetime
import hashlib


class RoomInit(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        room_alias = self.request.get('alias').lower()

        # First check if room with alias exists
        q = model.Room.query(model.Room.alias == room_alias)
        if q.count() != 1:
            # Create a new room with current user as participant
            room = model.Room()
            room.member.append(user)
            room.alias = room_alias
            room.put()
        else:
            # Check if current user has access to room
            room = q.get()
            if user not in room.member:
                logging.error('Access to room %s denied for %s' % (room_alias, user.nickname()))
                self.abort(403)

        participants = []
        for member in room.member:
            participants.append({
                'status': memcache.get(member.user_id() + room_alias),
                'nickname': member.nickname(),
                'email': member.email(),
                'hash': hashlib.md5(member.email()).hexdigest()
            })

        # Get some recent message if there are any
        messages = []
        q = model.Message.query(ancestor=room.key).order(-model.Message.timestamp).fetch(25)
        for msg in q:
            messages.append({
                'author': msg.author.nickname(),
                'message': msg.text,
                'timestamp': msg.timestamp.strftime("%Y%m%dT%H%M%SZ%Z"),
                'hash': hashlib.md5(msg.author.email()).hexdigest()
            })

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps({
            'alias': room_alias,
            'participants': participants,
            'messages': messages,
            'token': channel.create_channel("%s_%s" % (user.user_id(), room_alias)),
            'author': user.nickname()
        }))


class Message(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()

        # Send channel message to all room users
        data = json.loads(self.request.body)
        q = model.Room.query(model.Room.alias == data['alias'])
        if q.count() != 1:
            logging.error('No room found with alias: %s', data['alias'])
            self.abort(400)
        room = q.get()

        # Check if user has access to room
        if user not in room.member:
            logging.error('Access to room %s denied for %s' % (data['alias'], user.nickname()))
            self.abort(403)

        message_data = json.dumps({
            'type': 'message',
            'author': user.nickname(),
            'timestamp': datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ%Z"),
            'message': data['message'],
            'hash': hashlib.md5(user.email()).hexdigest()
        })
        for member in room.member:
            logging.info('Sending message to %s' % member.user_id())
            channel.send_message("%s_%s" % (member.user_id(), data['alias']), message_data)

        message = model.Message(parent=room.key)
        message.text = data['message']
        message.author = user
        message.put()

        self.response.headers['Content-Type'] = 'application/json'


class RoomInvite(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()

        data = json.loads(self.request.body)
        q = model.Room.query(model.Room.alias == data['alias'])
        if q.count() != 1:
            logging.error('No room found with alias: %s', data['alias'])
            self.abort(400)
        room = q.get()

        # Check if user has access to room
        if user not in room.member:
            logging.error('Access to room %s denied for %s' % (data['alias'], user.nickname()))
            self.abort(403)

        # Create user and add to room
        new_user = users.User(email=data['email'])
        room.member.append(new_user)
        room.put()

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps({
            'nickname': new_user.nickname(),
            'email': new_user.email(),
            'hash': hashlib.md5(new_user.email()).hexdigest()
        }))


class RoomRemove(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()

        data = json.loads(self.request.body)
        q = model.Room.query(model.Room.alias == data['alias'])
        if q.count() != 1:
            logging.error('No room found with alias: %s', data['alias'])
            self.abort(400)
        room = q.get()

        # Check if user has access to room
        if user not in room.member:
            logging.error('Access to room %s denied for %s' % (data['alias'], user.nickname()))
            self.abort(403)

        # Delete user from room
        new_user = users.User(email=data['email'])
        room.member.remove(new_user)
        room.put()

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps('OK'))


class ChannelConnected(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('from')
        logging.info('%s is connected' % client_id)
        memcache.set(client_id, True)

        # Send updated information to room
        id_str = client_id.split('_')
        room_alias = id_str[1]

        q = model.Room.query(model.Room.alias == room_alias)
        if q.count() != 1:
            logging.info('Did not find room alias "%s" from client_id' % room_alias)
            self.abort(200)
        room = q.get()

        status = []
        for member in room.member:
            status.append({
                'status': memcache.get("%s_%s" % (member.user_id(), room_alias)),
                'nickname': member.nickname(),
                'email': member.email(),
                'hash': hashlib.md5(member.email()).hexdigest()
            })
        for member in room.member:
            channel.send_message("%s_%s" % (member.user_id(), room_alias), json.dumps({
                'type': 'status',
                'members': status
            }))


class ChannelDisconnected(webapp2.RequestHandler):
    def post(self):
        client_id = self.request.get('from')
        logging.info('%s is disconnected' % client_id)
        memcache.set(client_id, None)

        # Send updated information to room
        id_str = client_id.split('_')
        room_alias = id_str[1]

        q = model.Room.query(model.Room.alias == room_alias)
        if q.count() != 1:
            logging.info('Did not find room alias "%s" from client_id' % room_alias)
            self.abort(200)
        room = q.get()

        status = []
        for member in room.member:
            status.append({
                'status': memcache.get("%s_%s" % (member.user_id(), room_alias)),
                'nickname': member.nickname(),
                'email': member.email(),
                'hash': hashlib.md5(member.email()).hexdigest()
            })
        for member in room.member:
            channel.send_message("%s_%s" % (member.user_id(), room_alias), json.dumps({
                'type': 'status',
                'members': status
            }))


app = webapp2.WSGIApplication([
                                          ('/api/room/init', RoomInit),
                                          ('/api/message', Message),
                                          ('/api/room/invite', RoomInvite),
                                          ('/api/room/remove', RoomRemove),
                                          ('/_ah/channel/connected/', ChannelConnected),
                                          ('/_ah/channel/disconnected/', ChannelDisconnected)
], debug=True)