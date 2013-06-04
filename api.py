from google.appengine.api import users
from google.appengine.api import channel
import model
import webapp2
import json
import logging
import datetime
import hashlib


class RoomInit(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        room_alias = self.request.get('alias')

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
                'nickname': member.nickname(),
                'email': member.email(),
                'hash': hashlib.md5(member.email()).hexdigest()
            })

        # Get some recent message if there are any
        messages = []
        q = model.Message.query(ancestor=room.key).order(-model.Message.timestamp).fetch(10)
        for msg in q:
            messages.append({
                'author': msg.author.nickname(),
                'message': msg.text,
                'timestamp': msg.timestamp.strftime("%m/%d/%Y %H:%M:%S UTC")
            })

        self.response.out.write(json.dumps({
            'alias': room_alias,
            'participants': participants,
            'messages': messages,
            'token': channel.create_channel(user.user_id()),
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
            'author': user.nickname(),
            'timestamp': datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S UTC"),
            'message': data['message']
        })
        for member in room.member:
            logging.info('Sending message to %s' % member.user_id())
            channel.send_message(member.user_id(), message_data)

        message = model.Message(parent=room.key)
        message.text = data['message']
        message.author = user
        message.put()


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

        self.response.out.write(json.dumps('OK'))


app = webapp2.WSGIApplication([
                                          ('/api/room/init', RoomInit),
                                          ('/api/message', Message),
                                          ('/api/room/invite', RoomInvite),
                                          ('/api/room/remove', RoomRemove)
], debug=True)