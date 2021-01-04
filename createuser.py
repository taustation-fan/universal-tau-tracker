import random
import string
import sys

from utt.model import db, Character, Token
from utt import app
from sqlalchemy.exc import IntegrityError

name = sys.argv[1]

def random_token():
    return ''.join(random.choices(string.ascii_letters, k=40))

def insert(name):
    character = Character(name=name)
    db.session.add(character)

    try:
        token_str = sys.argv[2]
    except IndexError:
        token_str = random_token()
    token = Token(character=character, token=token_str)
    db.session.add(token)
    db.session.commit()
    print('{} - {}'.format(name, token_str))

with app.app_context():
    db.create_all()

    character = Character.query.filter_by(name=name).first()
    if character:
        print('Character {} already exists, with these tokens:'.format(name))
        for token in character.tokens:
            print('   {}'.format(token.token))
    else:
        insert(name)
