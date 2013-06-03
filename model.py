from google.appengine.ext import ndb


class Message(ndb.Model):
    text = ndb.TextProperty()
    timestamp = ndb.DateTimeProperty(auto_now_add=True)
    author = ndb.UserProperty()


class Room(ndb.Model):
    alias = ndb.StringProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    member = ndb.UserProperty(repeated=True)